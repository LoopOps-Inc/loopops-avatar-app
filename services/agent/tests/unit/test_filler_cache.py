"""Stub TTS silence must not be reused after switching to a real voice provider."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from actinver_agent.avatar.fillers import FillerBank, filler_cache_voice_id
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
    tts = _CountingTts(pcm=b"\x01\x00" * 240)
    key = "filler:gemini_api:Puck:greet:opening"
    await cache.set(key, bytes(31_680), ttl_s=None)

    bank = FillerBank(tts=tts, cache=cache, voice_id="gemini_api:Puck", reject_silence=True)
    text, pcm = await bank.greeting("Ada")
    assert "Tino" in text
    assert tts.calls == 1
    assert pcm == tts.pcm
    assert await cache.get(key) == tts.pcm


@pytest.mark.asyncio
async def test_non_silent_cache_is_reused() -> None:
    cache = MemoryCache()
    cached = b"\x10\x00" * 120
    tts = _CountingTts(pcm=b"\xff\x7f" * 120)
    await cache.set("filler:gemini_api:Puck:greet:opening", cached, ttl_s=None)
    bank = FillerBank(tts=tts, cache=cache, voice_id="gemini_api:Puck", reject_silence=True)
    _, pcm = await bank.greeting("Ada")
    assert tts.calls == 0
    assert pcm == cached
