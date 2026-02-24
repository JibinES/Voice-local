"""WebSocket transport for browser-based voice chat."""

import asyncio
import base64
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketTransportHandler:
    """Manages WebSocket connections from the browser UI."""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self._closed = False

    async def accept(self):
        await self.ws.accept()

    async def send_transcript(self, text: str, language: str = ""):
        """Send ASR transcript to browser."""
        await self._send_json({
            "type": "transcript",
            "text": text,
            "language": language,
        })

    async def send_response(self, text: str):
        """Send LLM response text to browser."""
        await self._send_json({
            "type": "response",
            "text": text,
        })

    async def send_audio(self, audio_bytes: bytes, sample_rate: int = 24000):
        """Send TTS audio to browser as base64."""
        await self._send_json({
            "type": "audio",
            "data": base64.b64encode(audio_bytes).decode("utf-8"),
            "sample_rate": sample_rate,
            "format": "pcm16",
        })

    async def send_status(self, status: str):
        """Send pipeline status update (recording, transcribing, thinking, speaking)."""
        await self._send_json({
            "type": "status",
            "status": status,
        })

    async def send_error(self, message: str):
        """Send error message to browser."""
        await self._send_json({
            "type": "error",
            "message": message,
        })

    async def receive_audio(self) -> bytes | None:
        """Receive audio data from browser WebSocket."""
        try:
            data = await self.ws.receive()
            if "bytes" in data:
                return data["bytes"]
            elif "text" in data:
                msg = json.loads(data["text"])
                if msg.get("type") == "audio" and "data" in msg:
                    return base64.b64decode(msg["data"])
                elif msg.get("type") == "config":
                    return None  # Config messages handled separately
            return None
        except WebSocketDisconnect:
            self._closed = True
            return None

    async def receive_json(self) -> dict | None:
        """Receive JSON message from browser."""
        try:
            text = await self.ws.receive_text()
            return json.loads(text)
        except (WebSocketDisconnect, json.JSONDecodeError):
            self._closed = True
            return None

    @property
    def is_closed(self) -> bool:
        return self._closed

    async def close(self):
        if not self._closed:
            self._closed = True
            try:
                await self.ws.close()
            except Exception:
                pass

    async def _send_json(self, data: dict):
        if not self._closed:
            try:
                await self.ws.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                self._closed = True
