FROM voice-bot-vllm-base:latest

WORKDIR /app

# Copy configuration and startup script
COPY config.py /app/config.py
COPY start_vllm.sh /app/start_vllm.sh
RUN chmod +x /app/start_vllm.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/app/start_vllm.sh"]
