"""Per-client and per-device sliding-window rate limits (docs/01-architecture/06
§3.1). Exceeding a limit is a 429 with ``Retry-After``."""

from __future__ import annotations

from dataclasses import dataclass

from actinver_agent.config import Settings
from actinver_agent.ports import CachePort


@dataclass(frozen=True, slots=True)
class RateDecision:
    allowed: bool
    retry_after_s: int


class RateLimiter:
    def __init__(self, settings: Settings, cache: CachePort) -> None:
        self._limits = settings.limits
        self._cache = cache

    async def check_turn(self, *, client_id: str, device: str | None) -> RateDecision:
        minute_ok = await self._cache.sliding_window_hit(
            f"rl:{client_id}:1m", limit=self._limits.turns_per_minute, window_s=60
        )
        if not minute_ok:
            return RateDecision(False, 30)
        day_ok = await self._cache.sliding_window_hit(
            f"rl:{client_id}:1d", limit=self._limits.turns_per_day, window_s=86_400
        )
        if not day_ok:
            return RateDecision(False, 3600)
        if device:
            device_ok = await self._cache.sliding_window_hit(
                f"rl:dev:{device}:1m", limit=self._limits.turns_per_minute, window_s=60
            )
            if not device_ok:
                return RateDecision(False, 30)
        return RateDecision(True, 0)

    async def check_generic(self, *, key: str, limit: int, window_s: int) -> RateDecision:
        ok = await self._cache.sliding_window_hit(f"rl:{key}", limit=limit, window_s=window_s)
        return RateDecision(ok, 0 if ok else window_s)
