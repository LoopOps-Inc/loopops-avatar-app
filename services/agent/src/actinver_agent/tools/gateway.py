"""tool-gateway semantics as a library: caching at the freshness ceilings,
independent circuit breakers per tool, and fail-open vs fail-closed results
(docs/01-architecture/01 §3, §8; docs/04-backend/02 §3).

* Cache TTL == freshness ceiling. A cached value is never served beyond it.
* One breaker per tool, not per service: a slow news provider must not degrade a
  portfolio question.
* Bulkheads are upstream (separate httpx pools in ``clients/``); the gateway
  does not share state across tools.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import orjson
import structlog

from actinver_agent.graph.state import ToolResult
from actinver_agent.observability.setup import Metrics
from actinver_agent.ports import CachePort
from actinver_agent.tools.registry import ToolRegistry, _hash

log = structlog.get_logger(__name__)


@dataclass
class Breaker:
    failure_threshold: int = 3
    window_s: float = 60.0
    open_for_s: float = 30.0
    failures: deque[float] = field(default_factory=deque)
    opened_at: float | None = None

    def allow(self, now: float) -> bool:
        if self.opened_at is None:
            return True
        if now - self.opened_at >= self.open_for_s:
            # Half-open: allow one probe.
            self.opened_at = None
            self.failures.clear()
            return True
        return False

    def record(self, ok: bool, now: float) -> None:
        if ok:
            self.failures.clear()
            return
        self.failures.append(now)
        while self.failures and now - self.failures[0] > self.window_s:
            self.failures.popleft()
        if len(self.failures) >= self.failure_threshold:
            self.opened_at = now

    @property
    def is_open(self) -> bool:
        return self.opened_at is not None


class ToolGateway:
    def __init__(self, registry: ToolRegistry, cache: CachePort, metrics: Metrics) -> None:
        self.registry = registry
        self._cache = cache
        self._metrics = metrics
        self._breakers: dict[str, Breaker] = {}

    def breaker(self, name: str) -> Breaker:
        return self._breakers.setdefault(name, Breaker())

    async def call(self, name: str, *, client_id: str | None, args: dict[str, Any]) -> ToolResult:
        spec = self.registry.get(name)
        now = time.monotonic()
        scope = client_id if spec.requires_client else "public"
        cache_key = f"tool:{name}:{scope}:{_hash(args)}"

        if spec.cache_ttl_s > 0:
            cached = await self._read_cache(cache_key, spec.cache_ttl_s)
            if cached is not None:
                self._metrics.tool_calls.add(1, {"tool": name, "status": "cache_hit"})
                return ToolResult(
                    name=name,
                    ok=True,
                    data=cached["data"],
                    latency_ms=0,
                    cache_hit=True,
                    as_of=_iso(cached.get("as_of")),
                    args_hash=cached.get("args_hash"),
                    result_hash=cached.get("result_hash"),
                    classification=spec.classification,
                )

        breaker = self.breaker(name)
        if not breaker.allow(now):
            log.warning("tool.circuit_open", tool=name)
            self._metrics.tool_errors.add(1, {"tool": name, "reason": "CIRCUIT_OPEN"})
            return ToolResult(
                name=name, ok=False, error="CIRCUIT_OPEN", classification=spec.classification
            )

        result = await self.registry.call(name, client_id=client_id, args=args)
        breaker.record(result.ok, time.monotonic())
        if breaker.is_open:
            log.warning("tool.circuit_opened", tool=name)

        if result.ok and spec.cache_ttl_s > 0:
            await self._write_cache(cache_key, result, spec.cache_ttl_s)
        return result

    async def _read_cache(self, key: str, ttl_s: int) -> dict[str, Any] | None:
        try:
            raw = await self._cache.get(key)
        except Exception:
            return None
        if raw is None:
            return None
        try:
            entry = orjson.loads(raw)
        except orjson.JSONDecodeError:
            return None
        # Never serve beyond the freshness ceiling even if the store kept it.
        if time.time() - float(entry.get("stored_at", 0)) > ttl_s:
            return None
        return entry if isinstance(entry, dict) else None

    async def _write_cache(self, key: str, result: ToolResult, ttl_s: int) -> None:
        entry = {
            "stored_at": time.time(),
            "data": result.data,
            "as_of": result.as_of.isoformat() if result.as_of else None,
            "args_hash": result.args_hash,
            "result_hash": result.result_hash,
        }
        try:
            # Cached client data is encrypted at the application layer by the
            # cache adapter (docs/01-architecture/04 §3.3); the gateway stores bytes.
            await self._cache.set(key, orjson.dumps(entry, default=str), ttl_s=ttl_s)
        except Exception:
            log.warning("tool.cache_write_failed", tool=result.name)


def _iso(value: Any) -> Any:
    from datetime import datetime

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
