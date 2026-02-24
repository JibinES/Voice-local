FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11, pip, git, and curl
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && python -m pip install --upgrade pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install PyTorch nightly with CUDA 12.8 support
RUN pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128

# Build vLLM from source
ENV TORCH_CUDA_ARCH_LIST="12.0"
ENV VLLM_FLASH_ATTN_VERSION=2

RUN git clone https://github.com/vllm-project/vllm.git /opt/vllm \
    && cd /opt/vllm \
    && pip install -e .

WORKDIR /app

# Copy configuration and startup script
COPY config.py /app/config.py
COPY start_vllm.sh /app/start_vllm.sh
RUN chmod +x /app/start_vllm.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/app/start_vllm.sh"]
