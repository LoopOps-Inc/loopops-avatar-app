"""Text-to-speech via Google Cloud TTS producing PCM s16le mono @ 24 kHz.

Requesting 24 kHz directly means no resampling on the hot path
(docs/01-architecture/05 §3). Provider SDK imports live here only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import structlog
from google.cloud import texttospeech_v1 as tts

from actinver_agent.voice.framing import SAMPLE_RATE_HZ, strip_wav_header

log = structlog.get_logger(__name__)


class GoogleTextToSpeech:
    def __init__(
        self,
        *,
        voice_name: str = "es-MX-Neural2-A",
        language_code: str = "es-MX",
        speaking_rate: float = 1.0,
        sample_rate_hz: int = SAMPLE_RATE_HZ,
    ) -> None:
        self._client = tts.TextToSpeechAsyncClient()
        self._voice = tts.VoiceSelectionParams(language_code=language_code, name=voice_name)
        self._config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate_hz,
            speaking_rate=speaking_rate,
        )

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        response = await self._client.synthesize_speech(
            input=tts.SynthesisInput(text=text),
            voice=self._voice,
            audio_config=self._config,
        )
        yield strip_wav_header(response.audio_content)
