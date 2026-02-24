"""Tests for the LLM service."""

import os
import requests
import pytest

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-oss-20b")


def test_health():
    """LLM service health check."""
    resp = requests.get(f"{LLM_BASE_URL}/health", timeout=10)
    assert resp.status_code == 200


def test_models_endpoint():
    """List available models."""
    resp = requests.get(f"{LLM_BASE_URL}/v1/models", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    model_ids = [m["id"] for m in data["data"]]
    assert MODEL_NAME in model_ids, f"Model {MODEL_NAME} not found. Available: {model_ids}"


def test_chat_completion():
    """Test basic chat completion."""
    resp = requests.post(
        f"{LLM_BASE_URL}/v1/chat/completions",
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "user", "content": "Say hello in one sentence."}
            ],
            "max_tokens": 50,
            "temperature": 0.7,
        },
        timeout=60,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    content = data["choices"][0]["message"]["content"]
    assert len(content.strip()) > 0


def test_chat_completion_multilingual():
    """Test LLM with Hindi input."""
    resp = requests.post(
        f"{LLM_BASE_URL}/v1/chat/completions",
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Respond in Hindi."},
                {"role": "user", "content": "नमस्ते, आप कैसे हैं?"},
            ],
            "max_tokens": 100,
            "temperature": 0.7,
        },
        timeout=60,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["choices"][0]["message"]["content"].strip()) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
