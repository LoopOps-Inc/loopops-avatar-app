"""Redis 7 adapter: cache, rate limiting, concurrency slots, flags
(docs/01-architecture/04 §3.3)."""

from __future__ import annotations

import time
import uuid

import redis.asyncio as redis


class RedisCache:
    def __init__(self, url: str, *, timeout_s: float = 1.0) -> None:
        self._redis = redis.from_url(
            url, socket_timeout=timeout_s, socket_connect_timeout=timeout_s, decode_responses=False
        )

    async def aclose(self) -> None:
        await self._redis.aclose()

    async def get(self, key: str) -> bytes | None:
        value = await self._redis.get(key)
        if value is None:
            return None
        return value.encode() if isinstance(value, str) else bytes(value)

    async def set(self, key: str, value: bytes, *, ttl_s: int | None) -> None:
        if ttl_s:
            await self._redis.set(key, value, ex=ttl_s)
        else:
            await self._redis.set(key, value)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def incr(self, key: str, *, ttl_s: int | None = None) -> int:
        pipe = self._redis.pipeline()
        pipe.incr(key)
        if ttl_s:
            pipe.expire(key, ttl_s)
        result = await pipe.execute()
        return int(result[0])

    async def sliding_window_hit(self, key: str, *, limit: int, window_s: int) -> bool:
        now = time.time()
        member = f"{now:.6f}:{uuid.uuid4().hex[:8]}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_s)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, window_s + 1)
        _, _, count, _ = await pipe.execute()
        return int(count) <= limit

    async def acquire_slot(self, key: str, *, limit: int, member: str, ttl_s: int) -> bool:
        now = time.time()
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, now)  # drop expired slots
        pipe.zscore(key, member)
        pipe.zcard(key)
        _, existing, count = await pipe.execute()
        if existing is None and int(count) >= limit:
            return False
        await self._redis.zadd(key, {member: now + ttl_s})
        return True

    async def release_slot(self, key: str, *, member: str) -> None:
        await self._redis.zrem(key, member)

    async def slot_count(self, key: str) -> int:
        now = time.time()
        await self._redis.zremrangebyscore(key, 0, now)
        return int(await self._redis.zcard(key))

    async def get_flag(self, name: str) -> str | None:
        value = await self._redis.get(f"flags:{name}")
        if value is None:
            return None
        return value if isinstance(value, str) else bytes(value).decode()

    async def set_flag(self, name: str, value: str) -> None:
        await self._redis.set(f"flags:{name}", value)

    async def health(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except (redis.RedisError, OSError):
            return False
