FROM voice-bot-vllm-base:latest

ENV DEBIAN_FRONTEND=noninteractive

# Install additional TTS dependencies
RUN apt-get update && apt-get install -y \
    supervisor \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir snac fastapi uvicorn soundfile numpy aiohttp

# Clone svara-tts-inference repo for the FastAPI app code
RUN git clone --depth 1 https://github.com/Kenpath/svara-tts-inference.git /app \
    && rm -rf /app/.git

WORKDIR /app

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose FastAPI API port and internal vLLM port
EXPOSE 8002 8003

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8002/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
