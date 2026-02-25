FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.12 (required by speaches) and pip
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    git \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install speaches (formerly faster-whisper-server) and ctranslate2
RUN pip install --no-cache-dir \
    speaches[all]@git+https://github.com/fedirz/faster-whisper-server.git \
    ctranslate2

# Create model directory
RUN mkdir -p /models

WORKDIR /app

# Copy configuration
COPY config.yaml /app/config.yaml

ENV WHISPER__MODEL=/models/faster-whisper-large-v3
ENV WHISPER__COMPUTE_TYPE=int8
ENV WHISPER__INFERENCE_DEVICE=cuda
ENV WHISPER__DEVICE_INDEX=0
ENV WHISPER___UNSTABLE_VAD_FILTER=true
ENV STT_MODEL_TTL=-1
ENV VAD_MODEL_TTL=-1
ENV ENABLE_UI=false
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "--factory", "--host", "0.0.0.0", "--port", "8000", "speaches.main:create_app"]
