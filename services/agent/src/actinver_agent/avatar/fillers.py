"""Cached filler utterances (docs/01-architecture/01 §6, 03-mobile/03 §6).

About eight approved acknowledgement phrases, pre-synthesised once so they cost
zero TTS latency, rotated so they never become a tic, and logged as
system-generated - never counted as substantive content.
"""

from __future__ import annotations

import asyncio

import structlog

from actinver_agent.ports import CachePort, TextToSpeechPort
from actinver_agent.voice.framing import is_silent_pcm

log = structlog.get_logger(__name__)


def filler_cache_voice_id(*, provider: str, tts_voice_name: str, gemini_tts_voice: str) -> str:
    """Cache key namespace. Must change when the synthesizer changes, or stub
    silence (all-zero PCM) is replayed after switching to a real TTS provider."""
    if provider == "gemini_api":
        return f"gemini_api:{gemini_tts_voice}"
    return f"{provider}:{tts_voice_name}"


FILLER_PHRASES_ES: tuple[str, ...] = (
    "Déjame revisar tu portafolio.",
    "Un momento, lo consulto.",
    "Claro, lo reviso ahora mismo.",
    "Permíteme un segundo.",
    "Voy a verificar esa información.",
    "Dame un instante para confirmarlo.",
    "Estoy revisando los datos más recientes.",
    "Enseguida te digo.",
)

IDLE_PROMPT_ES = "¿Sigues ahí?"
CEILING_APOLOGY_ES = (
    "Disculpa, esto me está tomando más de lo esperado. Si prefieres, te comunico con tu asesor."
)
DURATION_WARNING_ES = "Esta sesión de voz está por terminar. ¿Quieres continuar?"


class FillerBank:
    def __init__(
        self,
        *,
        tts: TextToSpeechPort,
        cache: CachePort,
        voice_id: str,
        reject_silence: bool = False,
    ) -> None:
        self._tts = tts
        self._cache = cache
        self._voice = voice_id
        self._reject_silence = reject_silence
        self._pcm: list[bytes] = []
        self._special: dict[str, bytes] = {}
        self._index = 0
        self._locks: dict[str, asyncio.Lock] = {}

    async def warm(self) -> None:
        for n, phrase in enumerate(FILLER_PHRASES_ES):
            self._pcm.append(await self._synth_cached(f"filler:{self._voice}:{n}", phrase))
        for key, phrase in (
            ("idle", IDLE_PROMPT_ES),
            ("apology", CEILING_APOLOGY_ES),
            ("duration", DURATION_WARNING_ES),
        ):
            self._special[key] = await self._synth_cached(f"filler:{self._voice}:{key}", phrase)
        log.info("fillers.warmed", count=len(self._pcm))

    async def _synth_cached(self, key: str, phrase: str) -> bytes:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = await self._cache.get(key)
            if cached and not (self._reject_silence and is_silent_pcm(cached)):
                return cached
            if cached:
                log.warning("fillers.cache_silent", key=key, pcm_bytes=len(cached))
            chunks = [chunk async for chunk in self._tts.synthesize_stream(phrase)]
            pcm = b"".join(chunks)
            if pcm and not (self._reject_silence and is_silent_pcm(pcm)):
                await self._cache.set(key, pcm, ttl_s=None)
            elif self._reject_silence:
                log.warning("fillers.synth_silent", key=key, pcm_bytes=len(pcm))
            return pcm

    def next_filler(self) -> tuple[str, bytes]:
        if not self._pcm:
            return FILLER_PHRASES_ES[0], b""
        n = self._index % len(self._pcm)
        self._index += 1
        return FILLER_PHRASES_ES[n], self._pcm[n]

    def idle_prompt(self) -> tuple[str, bytes]:
        return IDLE_PROMPT_ES, self._special.get("idle", b"")

    def apology(self) -> tuple[str, bytes]:
        return CEILING_APOLOGY_ES, self._special.get("apology", b"")

    def duration_warning(self) -> tuple[str, bytes]:
        return DURATION_WARNING_ES, self._special.get("duration", b"")
