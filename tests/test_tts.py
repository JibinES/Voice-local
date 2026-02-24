"""Tests for the TTS (Text-to-Speech) service."""

import os
import requests
import pytest

TTS_BASE_URL = os.getenv("TTS_BASE_URL", "http://localhost:8002")


def test_health():
    """TTS service health check."""
    resp = requests.get(f"{TTS_BASE_URL}/health", timeout=10)
    assert resp.status_code == 200


def test_voices_endpoint():
    """List available voices."""
    resp = requests.get(f"{TTS_BASE_URL}/v1/voices", timeout=10)
    assert resp.status_code == 200


def test_synthesize_english():
    """Test TTS with English text."""
    resp = requests.post(
        f"{TTS_BASE_URL}/v1/text-to-speech",
        json={
            "text": "Hello, this is a test of the voice synthesis system.",
            "voice_id": "en_female",
            "stream": False,
            "output_format": "wav",
        },
        timeout=60,
    )
    assert resp.status_code == 200
    assert len(resp.content) > 1000, "Audio response too small"


def test_synthesize_hindi():
    """Test TTS with Hindi text."""
    resp = requests.post(
        f"{TTS_BASE_URL}/v1/text-to-speech",
        json={
            "text": "नमस्ते, यह एक परीक्षण है।",
            "voice_id": "hi_female",
            "stream": False,
            "output_format": "wav",
        },
        timeout=60,
    )
    assert resp.status_code == 200
    assert len(resp.content) > 1000


def test_synthesize_malayalam():
    """Test TTS with Malayalam text."""
    resp = requests.post(
        f"{TTS_BASE_URL}/v1/text-to-speech",
        json={
            "text": "നമസ്കാരം, സുഖമാണോ?",
            "voice_id": "ml_female",
            "stream": False,
            "output_format": "wav",
        },
        timeout=60,
    )
    assert resp.status_code == 200
    assert len(resp.content) > 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
