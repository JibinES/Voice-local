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

MAX_RETRIES=3

download_with_retry() {
    local cmd="$1"
    local desc="$2"
    local attempt=1

    while [ $attempt -le $MAX_RETRIES ]; do
        info "Downloading $desc (attempt $attempt/$MAX_RETRIES)..."
        if eval "$cmd"; then
            log "$desc downloaded successfully"
            return 0
        fi
        error "Failed to download $desc (attempt $attempt/$MAX_RETRIES)"
        attempt=$((attempt + 1))
        sleep 5
    done

    error "Failed to download $desc after $MAX_RETRIES attempts"
    return 1
}

# Ensure volume exists
docker volume create voice-bot-models 2>/dev/null || true

# Load HF_TOKEN from .env if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../.env" ]; then
    HF_TOKEN=$(grep -E "^HF_TOKEN=" "$SCRIPT_DIR/../.env" | cut -d= -f2- | xargs)
fi

# Prompt for token if not set
if [ -z "${HF_TOKEN:-}" ]; then
    warn "No HF_TOKEN found in .env"
    info "Some models may be gated or downloads may be rate-limited without a token."
    info "Get a token at: https://huggingface.co/settings/tokens"
    read -rp "Enter Hugging Face token (or press Enter to skip): " HF_TOKEN
fi

info "Downloading all models into Docker volume 'voice-bot-models'..."
info "Total download size: ~30-35GB. This may take a while."
echo ""

docker run --rm \
    -v voice-bot-models:/models \
    -e HF_HUB_ENABLE_HF_TRANSFER=1 \
    ${HF_TOKEN:+-e HF_TOKEN="$HF_TOKEN"} \
    python:3.11-slim bash -c '
set -e

pip install --quiet huggingface_hub[hf_transfer] ctranslate2 transformers

# Login if token is provided
if [ -n "${HF_TOKEN:-}" ]; then
    echo "Logging in to Hugging Face..."
    huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential 2>/dev/null || true
fi

echo ""
echo "=== [1/3] Downloading GPT-OSS-20B (~13GB) ==="
if [ -f /models/gpt-oss-20b/config.json ]; then
    echo "GPT-OSS-20B already downloaded, skipping."
else
    huggingface-cli download openai/gpt-oss-20b --local-dir /models/gpt-oss-20b
fi

echo ""
echo "=== [2/3] Downloading svara-TTS v1 (~13GB) ==="
if [ -f /models/svara-tts-v1/config.json ]; then
    echo "svara-TTS v1 already downloaded, skipping."
else
    huggingface-cli download kenpath/svara-tts-v1 --local-dir /models/svara-tts-v1
fi

echo ""
echo "=== [3/3] Downloading IndicWhisper + converting to CTranslate2 ==="
if [ -d /models/indicwhisper-ct2 ] && [ "$(ls -A /models/indicwhisper-ct2 2>/dev/null)" ]; then
    echo "IndicWhisper CT2 model already exists, skipping."
else
    echo "Downloading IndicWhisper HuggingFace checkpoint..."
    huggingface-cli download ai4bharat/indicwhisper --local-dir /models/indicwhisper-hf

    echo "Converting to CTranslate2 INT8 format..."
    ct2-whisper-converter \
        --model /models/indicwhisper-hf \
        --output_dir /models/indicwhisper-ct2 \
        --quantization int8

    echo "Cleaning up HuggingFace checkpoint..."
    rm -rf /models/indicwhisper-hf
fi

echo ""
echo "=== All models downloaded ==="
ls -la /models/
'

log "All models downloaded to Docker volume 'voice-bot-models'"
