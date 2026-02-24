#!/bin/bash
exec python -m vllm.entrypoints.openai.api_server \
    --model /models/gpt-oss-20b \
    --served-model-name gpt-oss-20b \
    --dtype auto \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.46875 \
    --port 8000 \
    --trust-remote-code \
    --enforce-eager
