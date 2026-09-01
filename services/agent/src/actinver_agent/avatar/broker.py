"""avatar-broker: LiveAvatar session lifecycle, cost controls and state.

Implements docs/01-architecture/05 §2, §5, §7 and §8:

* concurrency semaphore below the vendor ceiling (Redis-backed slots);
* per-client daily minute budget;
* keep-alive, token refresh at 80 % of TTL, hard cap with a 60 s warning;
* idle detection (prompt at 90 s, teardown at 150 s);
* 30 s teardown grace on backgrounding;
* idempotent stop that zeroises tokens and emits the billing metrics.

The ``livekit_agent_token`` lives only inside ``VendorSession`` in memory.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from actinver_agent.auth.context import RequestContext
from actinver_agent.avatar.fillers import FillerBank
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error
from actinver_agent.observability.setup import client_hash, get_metrics
from actinver_agent.ports import AvatarControlPort, AvatarSessionRecord, VendorSession

log = structlog.get_logger(__name__)

SLOT_KEY = "avatar:slots"
Notifier = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class ActiveSession:
    avatar_session_id: str
    client_id: str
    thread_id: str
    first_name: str
    consent_version: str
    vendor: VendorSession
    channel: AvatarControlPort
    started_at: datetime
    expires_at: datetime
    started_monotonic: float = field(default_factory=time.monotonic)
    last_client_activity: float = field(default_factory=time.monotonic)
    last_avatar_activity: float = field(default_factory=time.monotonic)
    idle_prompted: bool = False
    duration_warned: bool = False
    refreshed: bool = False
    greeted: bool = False
    ended: bool = False
    end_reason: str | None = None
    tasks: set[asyncio.Task[None]] = field(default_factory=set)
    current_turn: asyncio.Task[Any] | None = None
    background_task: asyncio.Task[None] | None = None
    notifier: Notifier | None = None
    speaking_seconds_extra: float = 0.0

    def touch_client(self) -> None:
        self.last_client_activity = time.monotonic()
        self.idle_prompted = False

    def touch_avatar(self) -> None:
        self.last_avatar_activity = time.monotonic()

    def cancel_turn(self) -> bool:
        if self.current_turn is not None and not self.current_turn.done():
            self.current_turn.cancel()
            return True
        return False

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_monotonic

    @property
    def speaking_seconds(self) -> float:
        return self.channel.speaking_seconds + self.speaking_seconds_extra

    async def notify(self, message: dict[str, Any]) -> None:
        if self.notifier is not None:
            with contextlib.suppress(Exception):
                await self.notifier(message)


class AvatarBroker:
    def __init__(self, deps: Dependencies, *, fillers: FillerBank | None = None) -> None:
        self._deps = deps
        self._fillers = fillers
        self._sessions: dict[str, ActiveSession] = {}
        self._settings = deps.settings.avatar
        self._limits = deps.settings.limits

    # ── Lookup ───────────────────────────────────────────────────────────────

    def get(self, avatar_session_id: str) -> ActiveSession | None:
        return self._sessions.get(avatar_session_id)

    def sessions_for_client(self, client_id: str) -> list[ActiveSession]:
        return [s for s in self._sessions.values() if s.client_id == client_id and not s.ended]

    # ── Start ────────────────────────────────────────────────────────────────

    async def preflight(self) -> dict[str, Any]:
        flags = self._deps.flags
        if await flags.kill_switch_active():
            return {
                "media_reachable": False,
                "estimated_rtt_ms": None,
                "voice_offered": False,
                "reason": "kill_switch",
            }
        if not (await flags.is_on("advisor.voice_mode") and await flags.is_on("advisor.avatar")):
            return {
                "media_reachable": False,
                "estimated_rtt_ms": None,
                "voice_offered": False,
                "reason": "voice_mode_disabled",
            }
        used = await self._deps.cache.slot_count(SLOT_KEY)
        if used >= self._settings.max_concurrent_sessions:
            return {
                "media_reachable": True,
                "estimated_rtt_ms": None,
                "voice_offered": False,
                "reason": "capacity",
            }
        reachable, rtt = await self._deps.avatar_vendor.preflight()
        return {
            "media_reachable": reachable,
            "estimated_rtt_ms": rtt,
            "voice_offered": reachable,
            "reason": None if reachable else "vendor_unreachable",
        }

    async def start(
        self,
        ctx: RequestContext,
        *,
        thread_id: str,
        first_name: str,
        consent_version: str,
        orientation: str = "portrait",
    ) -> ActiveSession:
        flags = self._deps.flags
        metrics = get_metrics()
        if await flags.kill_switch_active():
            raise api_error("KILL_SWITCH")
        if not (await flags.is_on("advisor.voice_mode") and await flags.is_on("advisor.avatar")):
            raise api_error("VOICE_UNAVAILABLE")

        used_minutes = await self._deps.repos.avatar_sessions.minutes_used_today(ctx.client_id)
        if used_minutes >= self._limits.avatar_minutes_per_day:
            raise api_error("AVATAR_BUDGET_EXHAUSTED")

        avatar_session_id = f"as_{uuid.uuid4().hex}"
        acquired = await self._deps.cache.acquire_slot(
            SLOT_KEY,
            limit=self._settings.max_concurrent_sessions,
            member=avatar_session_id,
            ttl_s=self._settings.max_session_duration_s + 60,
        )
        if not acquired:
            metrics.avatar_session_start_failures.add(1, {"reason": "capacity"})
            raise api_error("AVATAR_CAPACITY")

        try:
            vendor_session = await self._create_vendor_session()
            channel = self._deps.avatar_vendor.control_channel(vendor_session)
            await asyncio.wait_for(channel.open(), timeout=10)
        except Exception as exc:
            await self._deps.cache.release_slot(SLOT_KEY, member=avatar_session_id)
            metrics.avatar_session_start_failures.add(1, {"reason": type(exc).__name__})
            log.error("avatar.start_failed", reason=type(exc).__name__)
            raise api_error("VOICE_UNAVAILABLE", detail="avatar session could not start") from exc

        now = datetime.now(UTC)
        remaining_budget_s = max(60.0, (self._limits.avatar_minutes_per_day - used_minutes) * 60)
        duration_s = min(vendor_session.max_session_duration_s, int(remaining_budget_s))
        session = ActiveSession(
            avatar_session_id=avatar_session_id,
            client_id=ctx.client_id,
            thread_id=thread_id,
            first_name=first_name,
            consent_version=consent_version,
            vendor=vendor_session,
            channel=channel,
            started_at=now,
            expires_at=now + timedelta(seconds=duration_s),
        )
        self._sessions[avatar_session_id] = session
        await self._deps.repos.avatar_sessions.create(
            AvatarSessionRecord(
                avatar_session_id=avatar_session_id,
                client_id=ctx.client_id,
                thread_id=thread_id,
                vendor_session_id=vendor_session.session_id,
                started_at=now,
                ended_at=None,
                duration_s=0.0,
                speaking_s=0.0,
                end_reason=None,
            )
        )
        metrics.avatar_session_starts.add(1, {"orientation": orientation})
        self._spawn(session, self._watchdog(session))
        self._spawn(session, self._keep_alive_loop(session))
        log.info(
            "avatar.session_open",
            avatar_session_id=avatar_session_id,
            client_hash=client_hash(ctx.client_id),
            duration_cap_s=duration_s,
        )
        return session

    async def _create_vendor_session(self) -> VendorSession:
        """Retry once on transport errors; never more than twice on 401 (RB-04)."""
        last: Exception | None = None
        for attempt in range(2):
            try:
                return await self._deps.avatar_vendor.create_session()
            except Exception as exc:
                last = exc
                status = getattr(exc, "status", None)
                if status == 401 and attempt == 1:
                    log.error("avatar.api_key_rejected_twice")
                    break
                if status is not None and 400 <= int(status) < 500 and status != 401:
                    break
                await asyncio.sleep(0.2)
        assert last is not None
        raise last

    async def greet(self, session: ActiveSession) -> None:
        if self._fillers is None:
            return
        text, pcm = await self._fillers.greeting(session.first_name)
        await self.speak_system(session, text, pcm)

    async def speak_system(self, session: ActiveSession, text: str, pcm: bytes) -> None:
        """Play a system-generated utterance (filler, greeting, idle prompt)."""
        if session.ended or not pcm:
            return
        try:
            event_id = await session.channel.speak(pcm, flush=True)
            if event_id:
                await session.channel.speak_end(event_id)
            session.touch_avatar()
            await session.notify({"type": "caption", "text": text, "system": True})
        except Exception as exc:
            log.warning("avatar.system_speech_failed", reason=type(exc).__name__)

    # ── Lifecycle loops ──────────────────────────────────────────────────────

    async def _keep_alive_loop(self, session: ActiveSession) -> None:
        interval = self._settings.keep_alive_interval_s
        while True:
            await asyncio.sleep(interval)
            if _ended(session):
                return
            with contextlib.suppress(Exception):
                await session.channel.keep_alive()
                await self._deps.avatar_vendor.keep_alive(session.vendor)

    async def _watchdog(self, session: ActiveSession) -> None:
        cap = (session.expires_at - session.started_at).total_seconds()
        refresh_at = cap * self._settings.token_refresh_ratio
        while True:
            await asyncio.sleep(1.0)
            if _ended(session):
                return
            elapsed = session.elapsed_s
            idle = time.monotonic() - max(
                session.last_client_activity, session.last_avatar_activity
            )

            if idle >= self._settings.idle_teardown_s:
                await self.stop(session.avatar_session_id, reason="idle")
                return
            if idle >= self._settings.idle_prompt_s and not session.idle_prompted:
                session.idle_prompted = True
                if self._fillers is not None:
                    text, pcm = self._fillers.idle_prompt()
                    await self.speak_system(session, text, pcm)
                    session.last_avatar_activity = session.last_client_activity  # do not reset idle
            if not session.channel.connected:
                # Vendor closed the session (idle timeout, error or cap). Under the
                # cap we transparently start a new vendor session and keep the thread.
                if elapsed < cap - 5 and not session.refreshed:
                    await self._refresh(session)
                else:
                    await self.stop(session.avatar_session_id, reason="vendor_closed")
                    return
            if elapsed >= cap:
                await self.stop(session.avatar_session_id, reason="max_duration")
                return
            if elapsed >= cap - 60 and not session.duration_warned:
                session.duration_warned = True
                await session.notify(
                    {"type": "session.expiring", "seconds_left": int(cap - elapsed)}
                )
                if self._fillers is not None:
                    text, pcm = self._fillers.duration_warning()
                    await self.speak_system(session, text, pcm)
            if elapsed >= refresh_at and not session.refreshed:
                # Refresh at 80 % of the TTL so a session never outlives its credential.
                await self._refresh(session)

    async def _refresh(self, session: ActiveSession) -> None:
        session.refreshed = True
        try:
            new_vendor = await self._create_vendor_session()
            new_channel = self._deps.avatar_vendor.control_channel(new_vendor)
            await asyncio.wait_for(new_channel.open(), timeout=10)
        except Exception as exc:
            log.warning("avatar.refresh_failed", reason=type(exc).__name__)
            return
        old_vendor, old_channel = session.vendor, session.channel
        session.speaking_seconds_extra += old_channel.speaking_seconds
        session.vendor, session.channel = new_vendor, new_channel
        with contextlib.suppress(Exception):
            await old_channel.close()
            await self._deps.avatar_vendor.stop_session(old_vendor)
        _zeroise(old_vendor)
        payload = new_vendor.client_payload()
        await session.notify(
            {
                "type": "session.refreshed",
                "livekit_url": payload["livekit_url"],
                "livekit_client_token": payload["livekit_client_token"],
            }
        )
        log.info("avatar.session_refreshed", avatar_session_id=session.avatar_session_id)

    # ── Background grace ─────────────────────────────────────────────────────

    def background_grace(self, avatar_session_id: str) -> None:
        session = self._sessions.get(avatar_session_id)
        if session is None or session.ended or session.background_task is not None:
            return

        async def _grace() -> None:
            await asyncio.sleep(self._settings.background_grace_s)
            await self.stop(avatar_session_id, reason="background")

        session.background_task = asyncio.create_task(_grace())

    def cancel_background_grace(self, avatar_session_id: str) -> None:
        session = self._sessions.get(avatar_session_id)
        if session is None or session.background_task is None:
            return
        session.background_task.cancel()
        session.background_task = None
        session.touch_client()

    # ── Stop ─────────────────────────────────────────────────────────────────

    async def stop(self, avatar_session_id: str, *, reason: str) -> ActiveSession | None:
        session = self._sessions.get(avatar_session_id)
        if session is None:
            return None
        if session.ended:
            return session
        session.ended = True
        session.end_reason = reason
        session.cancel_turn()
        if session.background_task is not None:
            session.background_task.cancel()
        for task in list(session.tasks):
            if task is not asyncio.current_task():
                task.cancel()

        duration_s = session.elapsed_s
        speaking_s = session.speaking_seconds
        with contextlib.suppress(Exception):
            await session.channel.close()
        with contextlib.suppress(Exception):
            await self._deps.avatar_vendor.stop_session(session.vendor)
        _zeroise(session.vendor)
        await self._deps.cache.release_slot(SLOT_KEY, member=avatar_session_id)
        with contextlib.suppress(Exception):
            await self._deps.repos.avatar_sessions.finish(
                avatar_session_id,
                ended_at=datetime.now(UTC),
                duration_s=duration_s,
                speaking_s=speaking_s,
                end_reason=reason,
            )

        metrics = get_metrics()
        metrics.avatar_session_duration_s.record(duration_s, {"reason": reason})
        metrics.avatar_session_speaking_s.record(speaking_s, {"reason": reason})
        metrics.avatar_credits.add(max(1, math.ceil(duration_s / 60)), {"mode": "LITE"})
        if session.channel.first_frame_ms is not None:
            metrics.avatar_first_frame_ms.record(session.channel.first_frame_ms)
        ratio = speaking_s / duration_s if duration_s > 0 else 0.0
        log.info(
            "avatar.session_closed",
            avatar_session_id=avatar_session_id,
            reason=reason,
            duration_s=round(duration_s, 1),
            speaking_s=round(speaking_s, 1),
            speaking_ratio=round(ratio, 3),
        )
        await session.notify({"type": "session.closed", "reason": reason})
        self._sessions.pop(avatar_session_id, None)
        return session

    async def stop_all_for_client(self, client_id: str, *, reason: str) -> int:
        count = 0
        for session in self.sessions_for_client(client_id):
            await self.stop(session.avatar_session_id, reason=reason)
            count += 1
        return count

    async def stop_all(self, *, reason: str) -> None:
        for session_id in list(self._sessions):
            await self.stop(session_id, reason=reason)

    def _spawn(self, session: ActiveSession, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        session.tasks.add(task)
        task.add_done_callback(session.tasks.discard)


def _zeroise(vendor: VendorSession) -> None:
    vendor.session_token = ""
    vendor.livekit_agent_token = ""
    vendor.livekit_client_token = ""
    vendor.ws_url = ""


def _ended(session: ActiveSession) -> bool:
    """Read through a call so the type checker does not narrow across awaits."""
    return bool(session.ended)
