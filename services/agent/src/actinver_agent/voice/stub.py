"""Stub voice adapters for local development and CI.

``StubSpeechToText`` never transcribes audio: transcripts arrive through the
dev-only ``dev.transcript`` WebSocket message (documented in the API). It still
consumes audio frames so the storage path is exercised.

``StubTextToSpeech`` yields silence proportional to the text length so the
framing, pacing and speaking-seconds accounting behave like real audio.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from actinver_agent.ports import Transcript
from actinver_agent.voice.framing import BYTES_PER_SECOND

_MS_PER_WORD = 60


class StubSpeechToText:
    def __init__(self, *, language: str = "es-MX") -> None:
        self._language = language
        self._queue: asyncio.Queue[Transcript | None] = asyncio.Queue()

    def push_text(self, text: str, confidence: float = 0.95, *, is_final: bool = True) -> None:
        self._queue.put_nowait(
            Transcript(text=text, is_final=is_final, confidence=confidence, language=self._language)
        )

    def close(self) -> None:
        self._queue.put_nowait(None)

    async def stream(self, audio_frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        async def drain() -> None:
            async for _ in audio_frames:
                pass

        drain_task = asyncio.create_task(drain())
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    return
                yield item
        finally:
            drain_task.cancel()


class StubTextToSpeech:
    def __init__(self, *, ms_per_word: int = _MS_PER_WORD) -> None:
        self._ms_per_word = ms_per_word

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        words = max(1, len(text.split()))
        total_bytes = BYTES_PER_SECOND * words * self._ms_per_word // 1000
        total_bytes -= total_bytes % 2
        step = BYTES_PER_SECOND // 4  # 250 ms slices
        emitted = 0
        while emitted < total_bytes:
            size = min(step, total_bytes - emitted)
            emitted += size
            yield bytes(size)
            await asyncio.sleep(0)
