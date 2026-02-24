#!/bin/bash
set -euo pipefail

# =============================================================================
# Download all model weights into the shared Docker volume
# =============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error(){ echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

# Ensure volume exists
docker volume create voice-bot-models >/dev/null 2>&1 || true

# Load HF_TOKEN from .env if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HF_TOKEN=""
if [ -f "$SCRIPT_DIR/../.env" ]; then
    # Read token safely without shell expansion issues
    HF_TOKEN=$(grep -E "^HF_TOKEN=" "$SCRIPT_DIR/../.env" | sed 's/^HF_TOKEN=//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
fi

# Prompt for token if not set or is placeholder
if [ -z "$HF_TOKEN" ] || [ "$HF_TOKEN" = "hf_your_token_here" ]; then
    warn "No HF_TOKEN found in .env"
    info "Some models may be gated or downloads may be rate-limited without a token."
    info "Get a token at: https://huggingface.co/settings/tokens"
    read -rp "Enter Hugging Face token (or press Enter to skip): " HF_TOKEN
fi

info "Downloading all models into Docker volume 'voice-bot-models'..."
info "Total download size: ~30-35GB. This may take a while."
echo ""

# Build docker run args — pass HF_TOKEN only if non-empty
DOCKER_ARGS=( --rm -v voice-bot-models:/models )
if [ -n "$HF_TOKEN" ]; then
    DOCKER_ARGS+=( -e "HF_TOKEN=$HF_TOKEN" )
fi

docker run "${DOCKER_ARGS[@]}" python:3.11-slim bash -c '
set -e

echo "Installing dependencies..."
pip install --quiet huggingface_hub hf_transfer ctranslate2 transformers
export HF_HUB_ENABLE_HF_TRANSFER=1

# Login if token is provided
if [ -n "${HF_TOKEN:-}" ]; then
    echo "Logging in to Hugging Face..."
    python3 -c "from huggingface_hub import login; login(token=\"${HF_TOKEN}\", add_to_git_credential=False)" 2>/dev/null || echo "Warning: HF login failed, continuing anyway..."
fi

echo ""
echo "=== [1/3] Downloading GPT-OSS-20B (~13GB) ==="
if [ -f /models/gpt-oss-20b/config.json ]; then
    echo "GPT-OSS-20B already downloaded, skipping."
else
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(\"openai/gpt-oss-20b\", local_dir=\"/models/gpt-oss-20b\")
"
fi

echo ""
echo "=== [2/3] Downloading svara-TTS v1 (~13GB) ==="
if [ -f /models/svara-tts-v1/config.json ]; then
    echo "svara-TTS v1 already downloaded, skipping."
else
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(\"kenpath/svara-tts-v1\", local_dir=\"/models/svara-tts-v1\")
"
fi

echo ""
echo "=== [3/3] Downloading IndicWhisper + converting to CTranslate2 ==="
if [ -d /models/indicwhisper-ct2 ] && [ "$(ls -A /models/indicwhisper-ct2 2>/dev/null)" ]; then
    echo "IndicWhisper CT2 model already exists, skipping."
else
    echo "Downloading IndicWhisper HuggingFace checkpoint..."
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(\"ai4bharat/indicwhisper\", local_dir=\"/models/indicwhisper-hf\")
"

    echo "Converting to CTranslate2 INT8 format..."
    ct2-transformers-converter \
        --model /models/indicwhisper-hf \
        --output_dir /models/indicwhisper-ct2 \
        --quantization int8 \
        --force

    echo "Cleaning up HuggingFace checkpoint..."
    rm -rf /models/indicwhisper-hf
fi

echo ""
echo "=== All models downloaded ==="
ls -la /models/
'

log "All models downloaded to Docker volume 'voice-bot-models'"
