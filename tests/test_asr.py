"""Tests for the ASR (Automatic Speech Recognition) service."""

import os
import requests
import pytest

ASR_BASE_URL = os.getenv("ASR_BASE_URL", "http://localhost:8001")


def test_health():
    """ASR service health check."""
    resp = requests.get(f"{ASR_BASE_URL}/health", timeout=10)
    assert resp.status_code == 200


def test_transcription_endpoint_exists():
    """Verify the transcription endpoint accepts POST requests."""
    # Send empty request to check endpoint exists (expect 4xx, not 5xx)
    resp = requests.post(f"{ASR_BASE_URL}/v1/audio/transcriptions", timeout=10)
    assert resp.status_code in (400, 422), f"Unexpected status: {resp.status_code}"


def test_transcription_with_audio():
    """Test transcription with a sample audio file."""
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_audio")
    audio_files = [f for f in os.listdir(sample_dir) if f.endswith(".wav")] if os.path.exists(sample_dir) else []

    if not audio_files:
        pytest.skip("No sample audio files found in tests/sample_audio/")

    audio_path = os.path.join(sample_dir, audio_files[0])
    with open(audio_path, "rb") as f:
        resp = requests.post(
            f"{ASR_BASE_URL}/v1/audio/transcriptions",
            files={"file": ("audio.wav", f, "audio/wav")},
            data={"model": "indicwhisper"},
            timeout=30,
        )

    assert resp.status_code == 200
    result = resp.json()
    assert "text" in result
    assert len(result["text"].strip()) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
