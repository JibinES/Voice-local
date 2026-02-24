"""Voice Bot Orchestrator — Pipecat pipeline connecting ASR, LLM, and TTS."""

import asyncio
import base64
import io
import logging
import tempfile

import aiohttp
import soundfile as sf
import uvicorn
from fastapi import FastAPI, WebSocket, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from config import (
    ASR_BASE_URL,
    TTS_BASE_URL,
    LLM_BASE_URL,
    LLM_MODEL_NAME,
    ORCHESTRATOR_PORT,
    DEFAULT_VOICE,
    SYSTEM_PROMPT,
)
from language_router import get_voice_id
from svara_tts_service import SvaraTTSService
from transport import WebSocketTransportHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Bot Orchestrator")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator"}


@app.get("/health/all")
async def health_all():
    """Check health of all downstream services."""
    services = {
        "asr": f"{ASR_BASE_URL}/health",
        "tts": f"{TTS_BASE_URL}/health",
        "llm": f"{LLM_BASE_URL}/health",
    }
    results = {}
    async with aiohttp.ClientSession() as session:
        for name, url in services.items():
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    results[name] = {"status": "healthy" if resp.status == 200 else "unhealthy", "code": resp.status}
            except Exception as e:
                results[name] = {"status": "unhealthy", "error": str(e)}
    results["orchestrator"] = {"status": "healthy"}
    return results


# ---------------------------------------------------------------------------
# ASR helper
# ---------------------------------------------------------------------------
async def transcribe_audio(audio_bytes: bytes, language: str = "") -> dict:
    """Send audio to ASR service and get transcription."""
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("file", audio_bytes, filename="audio.wav", content_type="audio/wav")
        data.add_field("model", "indicwhisper")
        if language:
            data.add_field("language", language)

        async with session.post(
            f"{ASR_BASE_URL}/v1/audio/transcriptions",
            data=data,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                return {
                    "text": result.get("text", ""),
                    "language": result.get("language", ""),
                }
            else:
                error = await resp.text()
                logger.error(f"ASR error {resp.status}: {error}")
                return {"text": "", "language": "", "error": error}


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------
async def generate_response(text: str, conversation_history: list) -> str:
    """Send text to LLM and get response."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": text})

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json={
                "model": LLM_MODEL_NAME,
                "messages": messages,
                "max_tokens": 512,
                "temperature": 0.7,
            },
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                return result["choices"][0]["message"]["content"]
            else:
                error = await resp.text()
                logger.error(f"LLM error {resp.status}: {error}")
                return "I'm sorry, I couldn't generate a response."


# ---------------------------------------------------------------------------
# TTS helper
# ---------------------------------------------------------------------------
async def synthesize_speech(text: str, voice_id: str = DEFAULT_VOICE) -> bytes:
    """Send text to TTS and get audio bytes."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{TTS_BASE_URL}/v1/text-to-speech",
            json={
                "text": text,
                "voice_id": voice_id,
                "stream": False,
                "output_format": "wav",
            },
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                error = await resp.text()
                logger.error(f"TTS error {resp.status}: {error}")
                return b""


# ---------------------------------------------------------------------------
# WebSocket endpoint for real-time voice chat
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_voice_chat(ws: WebSocket):
    transport = WebSocketTransportHandler(ws)
    await transport.accept()
    logger.info("WebSocket client connected")

    conversation_history = []
    selected_language = ""

    try:
        while not transport.is_closed:
            msg = await transport.receive_json()
            if msg is None:
                break

            msg_type = msg.get("type", "")

            if msg_type == "config":
                selected_language = msg.get("language", "")
                logger.info(f"Language set to: {selected_language}")
                continue

            if msg_type == "audio":
                audio_data = base64.b64decode(msg["data"]) if "data" in msg else None
                if not audio_data:
                    continue

                # Step 1: Transcribe
                await transport.send_status("transcribing")
                asr_result = await transcribe_audio(audio_data, selected_language)
                transcript = asr_result.get("text", "")
                detected_lang = asr_result.get("language", selected_language)

                if not transcript.strip():
                    await transport.send_status("idle")
                    continue

                await transport.send_transcript(transcript, detected_lang)

                # Step 2: Generate LLM response
                await transport.send_status("thinking")
                response_text = await generate_response(transcript, conversation_history)
                await transport.send_response(response_text)

                # Update conversation history
                conversation_history.append({"role": "user", "content": transcript})
                conversation_history.append({"role": "assistant", "content": response_text})

                # Keep history manageable
                if len(conversation_history) > 20:
                    conversation_history = conversation_history[-20:]

                # Step 3: Synthesize speech
                await transport.send_status("speaking")
                voice_id = get_voice_id(detected_lang or selected_language)
                audio_bytes = await synthesize_speech(response_text, voice_id)

                if audio_bytes:
                    await transport.send_audio(audio_bytes)

                await transport.send_status("idle")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await transport.send_error(str(e))
    finally:
        await transport.close()
        logger.info("WebSocket client disconnected")


# ---------------------------------------------------------------------------
# REST endpoint for single-turn voice chat
# ---------------------------------------------------------------------------
@app.post("/v1/voice/chat")
async def voice_chat_rest(
    audio: UploadFile = File(...),
    language: str = Form(""),
):
    """Single-turn voice interaction: audio in -> audio out."""
    audio_bytes = await audio.read()

    # Transcribe
    asr_result = await transcribe_audio(audio_bytes, language)
    transcript = asr_result.get("text", "")
    detected_lang = asr_result.get("language", language)

    if not transcript.strip():
        return {"error": "No speech detected"}

    # Generate response
    response_text = await generate_response(transcript, [])

    # Synthesize
    voice_id = get_voice_id(detected_lang)
    audio_response = await synthesize_speech(response_text, voice_id)

    return StreamingResponse(
        io.BytesIO(audio_response),
        media_type="audio/wav",
        headers={
            "X-Transcript": transcript,
            "X-Response-Text": response_text,
            "X-Language": detected_lang,
        },
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=ORCHESTRATOR_PORT)
