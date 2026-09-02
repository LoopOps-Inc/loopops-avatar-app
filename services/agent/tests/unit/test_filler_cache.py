"""Stub TTS silence must not be reused after switching to a real voice provider."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from actinver_agent.avatar.fillers import FILLER_PHRASES_ES, FillerBank, filler_cache_voice_id
from actinver_agent.persistence.memory import MemoryCache
from actinver_agent.voice.framing import is_silent_pcm


def test_stub_pcm_is_detected_as_silent() -> None:
    silence = bytes(31_680)
    assert is_silent_pcm(silence)
    peaked = bytearray(silence)
    peaked[100] = 0x7F
    peaked[101] = 0x00
    assert not is_silent_pcm(bytes(peaked))


def test_filler_cache_voice_id_changes_with_provider() -> None:
    stub = filler_cache_voice_id(
        provider="stub", tts_voice_name="es-MX-Neural2-A", gemini_tts_voice="Puck"
    )
    gemini = filler_cache_voice_id(
        provider="gemini_api", tts_voice_name="es-MX-Neural2-A", gemini_tts_voice="Puck"
    )
    assert stub != gemini
    assert gemini.startswith("gemini_api:")


class _CountingTts:
    def __init__(self, pcm: bytes) -> None:
        self.pcm = pcm
        self.calls = 0

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        self.calls += 1
        _ = text
        yield self.pcm


@pytest.mark.asyncio
async def test_silent_cache_is_ignored_when_rejecting_silence() -> None:
    cache = MemoryCache()
    tts = _CountingTts(pcm=b"\x7f\x00" * 240)  # every sample is 127, above the silence floor
    key = "filler:gemini_api:Puck:0"
    await cache.set(key, bytes(31_680), ttl_s=None)

    bank = FillerBank(tts=tts, cache=cache, voice_id="gemini_api:Puck", reject_silence=True)
    await bank.warm()
    assert tts.calls == len(FILLER_PHRASES_ES) + 3, "the silent cached clip is re-synthesised"
    _, pcm = bank.next_filler()
    assert pcm == tts.pcm
    assert await cache.get(key) == tts.pcm


@pytest.mark.asyncio
async def test_non_silent_cache_is_reused() -> None:
    cache = MemoryCache()
    cached = b"\x80\x00" * 120  # every sample is 128, above the silence floor
    tts = _CountingTts(pcm=b"\xff\x7f" * 120)
    await cache.set("filler:gemini_api:Puck:0", cached, ttl_s=None)
    bank = FillerBank(tts=tts, cache=cache, voice_id="gemini_api:Puck", reject_silence=True)
    await bank.warm()
    assert tts.calls == len(FILLER_PHRASES_ES) + 3 - 1, "only the cached clip is skipped"
    _, pcm = bank.next_filler()
    assert pcm == cached
