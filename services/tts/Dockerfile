FROM voice-bot-vllm-base:latest

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    supervisor \
    ffmpeg \
    libsndfile1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Clone svara-tts-inference repo
RUN git clone --depth 1 https://github.com/Kenpath/svara-tts-inference.git /app \
    && rm -rf /app/.git

WORKDIR /app

# Install Python dependencies from repo's requirements.txt
# Skip torch/vllm/flashinfer (already in base image) to avoid conflicts
RUN grep -v -E '^(torch$|torchaudio|vllm|flashinfer)' requirements.txt > /tmp/filtered-requirements.txt \
    && pip install --no-cache-dir -r /tmp/filtered-requirements.txt \
    && pip install --no-cache-dir soundfile numpy \
    && rm /tmp/filtered-requirements.txt

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose FastAPI API port and internal vLLM port
EXPOSE 8002 8003

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
