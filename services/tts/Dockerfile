FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    supervisor \
    ffmpeg \
    git \
    curl \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && python -m pip install --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch nightly with CUDA 12.8 support
RUN pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128

# Build vLLM from source with Blackwell architecture support
RUN git clone https://github.com/vllm-project/vllm.git /tmp/vllm && \
    cd /tmp/vllm && \
    TORCH_CUDA_ARCH_LIST="12.0" VLLM_FLASH_ATTN_VERSION=2 pip install -e . && \
    rm -rf /tmp/vllm/.git

# Install Python dependencies
RUN pip install snac fastapi uvicorn soundfile numpy aiohttp

# Clone svara-tts-inference repo for the FastAPI app code
RUN git clone https://github.com/ai4bharat/svara-tts-inference.git /app && \
    rm -rf /app/.git

WORKDIR /app

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose FastAPI API port and internal vLLM port
EXPOSE 8002 8003

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
