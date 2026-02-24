"""Custom Pipecat TTS service for svara-TTS v1 API."""

import aiohttp
import struct
from typing import AsyncGenerator

from pipecat.frames.frames import (
    AudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    ErrorFrame,
)
from pipecat.services.ai_services import TTSService


class SvaraTTSService(TTSService):
    """Pipecat TTS adapter for svara-TTS v1 streaming API."""

    def __init__(
        self,
        *,
        base_url: str = "http://tts:8002",
        voice_id: str = "hi_female",
        output_format: str = "pcm",
        sample_rate: int = 24000,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._base_url = base_url.rstrip("/")
        self._voice_id = voice_id
        self._output_format = output_format
        self._session: aiohttp.ClientSession | None = None

    def set_voice(self, voice_id: str):
        self._voice_id = voice_id

    async def set_model(self, model: str):
        pass  # Single model, no switching needed

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def run_tts(self, text: str) -> AsyncGenerator:
        """Generate speech from text using svara-TTS streaming API."""
        await self.push_frame(TTSStartedFrame())

        try:
            session = await self._get_session()
            payload = {
                "text": text,
                "voice_id": self._voice_id,
                "stream": True,
                "output_format": self._output_format,
            }

            async with session.post(
                f"{self._base_url}/v1/text-to-speech",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    await self.push_frame(
                        ErrorFrame(f"TTS error {response.status}: {error_text}")
                    )
                    return

                async for chunk in response.content.iter_chunked(4096):
                    if chunk:
                        await self.push_frame(
                            AudioRawFrame(
                                audio=chunk,
                                sample_rate=self._sample_rate,
                                num_channels=1,
                            )
                        )
                        yield  # Yield control back to pipeline

        except aiohttp.ClientError as e:
            await self.push_frame(ErrorFrame(f"TTS connection error: {e}"))
        finally:
            await self.push_frame(TTSStoppedFrame())

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        await super().close()
