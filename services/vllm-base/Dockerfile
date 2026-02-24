FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.12, pip, git, and build essentials
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    git \
    curl \
    build-essential \
    cmake \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install PyTorch nightly with CUDA 12.8 (required for Blackwell sm_120)
RUN pip install --no-cache-dir --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128

# Build vLLM from source for Blackwell (sm_120)
ENV TORCH_CUDA_ARCH_LIST="12.0"
ENV VLLM_FLASH_ATTN_VERSION=2
ENV MAX_JOBS=6

RUN git clone --depth 1 https://github.com/vllm-project/vllm.git /opt/vllm \
    && cd /opt/vllm \
    && python use_existing_torch.py \
    && pip install --no-cache-dir -r requirements/build.txt \
    && pip install --no-cache-dir --no-build-isolation -e . \
    && rm -rf /opt/vllm/.git
