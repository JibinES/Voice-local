#!/bin/bash
set -euo pipefail

# =============================================================================
# Voice Bot — One-Click Deployment Script
# =============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
info()  { echo -e "${BLUE}[→]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  Voice Bot — Multilingual Voice Agent Deployment"
echo "============================================================"
echo ""

# ─────────────────────────────────────────────────────────────────
# Step 1: Pre-flight checks
# ─────────────────────────────────────────────────────────────────
info "Running pre-flight checks..."

# Check Docker
if ! command -v docker &>/dev/null; then
    error "Docker is not installed. Install Docker first."
    exit 1
fi
log "Docker found: $(docker --version)"

# Check Docker Compose
if ! docker compose version &>/dev/null; then
    error "Docker Compose (v2) not found. Install docker-compose-plugin."
    exit 1
fi
log "Docker Compose found: $(docker compose version --short)"

# Check NVIDIA driver
if ! command -v nvidia-smi &>/dev/null; then
    error "nvidia-smi not found. Install NVIDIA driver (570.x+)."
    exit 1
fi

DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits | head -1)
log "NVIDIA driver: $DRIVER_VERSION"

# Check GPU
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
log "GPU detected: $GPU_NAME ($GPU_MEMORY)"

# Quick GPU access check (uses existing image if cached, skips pull)
if docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
    log "Docker GPU access verified"
else
    warn "Could not verify Docker GPU access. Continuing — containers may still work."
fi

echo ""

# ─────────────────────────────────────────────────────────────────
# Step 2: Create model cache volume
# ─────────────────────────────────────────────────────────────────
info "Creating model cache volume..."
docker volume create voice-bot-models >/dev/null 2>&1 || true
log "Volume 'voice-bot-models' ready"
echo ""

# ─────────────────────────────────────────────────────────────────
# Step 3: Download all models
# ─────────────────────────────────────────────────────────────────
info "Downloading models (this may take a while on first run)..."
if ! bash scripts/download_models.sh; then
    error "Model download failed. Check your HF_TOKEN in .env and network connection."
    error "You can retry just the download with: bash scripts/download_models.sh"
    exit 1
fi
echo ""

# ─────────────────────────────────────────────────────────────────
# Step 4: Build Docker images
# ─────────────────────────────────────────────────────────────────
info "Building Docker images..."
docker compose build
log "All images built successfully"
echo ""

# ─────────────────────────────────────────────────────────────────
# Step 5: Start all services
# ─────────────────────────────────────────────────────────────────
info "Starting all services..."
docker compose up -d
log "All services starting"
echo ""

# ─────────────────────────────────────────────────────────────────
# Step 6: Wait for health checks
# ─────────────────────────────────────────────────────────────────
info "Waiting for services to become healthy..."

SERVICES=("voice-bot-asr:8001" "voice-bot-tts:8002" "voice-bot-llm:8000" "voice-bot-orchestrator:9000" "voice-bot-ui:3000")
MAX_WAIT=300
INTERVAL=10

for svc_port in "${SERVICES[@]}"; do
    svc="${svc_port%%:*}"
    port="${svc_port##*:}"
    elapsed=0

    while [ $elapsed -lt $MAX_WAIT ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "not_found")
        if [ "$status" = "healthy" ]; then
            log "$svc is healthy (port $port)"
            break
        fi
        sleep $INTERVAL
        elapsed=$((elapsed + INTERVAL))
        info "Waiting for $svc... ($elapsed/${MAX_WAIT}s)"
    done

    if [ $elapsed -ge $MAX_WAIT ]; then
        warn "$svc did not become healthy within ${MAX_WAIT}s"
    fi
done

echo ""

# ─────────────────────────────────────────────────────────────────
# Step 7: Print status
# ─────────────────────────────────────────────────────────────────
echo "============================================================"
echo "  Voice Bot — Service Status"
echo "============================================================"
echo ""
echo "  Service URLs:"
echo "    LLM:          http://localhost:8000"
echo "    ASR:          http://localhost:8001"
echo "    TTS:          http://localhost:8002"
echo "    Orchestrator: http://localhost:9000"
echo "    Test UI:      http://localhost:3000"
echo ""
echo "  WebSocket:      ws://localhost:9000/ws"
echo "  REST API:       POST http://localhost:9000/v1/voice/chat"
echo ""

info "VRAM usage:"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
echo ""

log "Deployment complete! Open http://localhost:3000 in your browser."
