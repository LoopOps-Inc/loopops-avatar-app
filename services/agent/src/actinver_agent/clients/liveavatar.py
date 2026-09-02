"""LiveAvatar (HeyGen) LITE-mode vendor adapter (ADR-0001, docs/01-architecture/05).

Vendor reference: https://docs.liveavatar.com/ (lite-mode/lifecycle, lite-mode/events,
api-reference/sessions/*), verified 2026-09-01.

Two things this module must never do:
  * expose ``X-API-KEY`` or ``livekit_agent_token`` outside this process;
  * send audio in any format other than PCM s16le mono @ 24 kHz, base64-encoded.

Only httpx and websockets are used here; no vendor SDK.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import re
import time
import uuid
from collections.abc import Coroutine
from enum import StrEnum
from typing import Any

import httpx
import structlog
import websockets

from actinver_agent.config import LiveAvatarSettings
from actinver_agent.ports import VendorSession
from actinver_agent.voice.framing import MAX_PACKET_BYTES, chunk_bytes_for, looks_like_pcm16

log = structlog.get_logger(__name__)


class SessionState(StrEnum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"
    CLOSED = "closed"


class AvatarState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class LiveAvatarError(RuntimeError):
    def __init__(
        self, message: str, *, status: int | None = None, duration_cap_s: int | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        # Set when the vendor rejected ``max_session_duration`` and told us its cap.
        self.duration_cap_s = duration_cap_s


_DURATION_CAP_RE = re.compile(r"max_session_duration.*?maximum allowed \((\d+)s\)")


def _duration_cap(response: httpx.Response) -> int | None:
    """Extract the vendor's session-duration cap from a 400 body, nothing else.

    Sandbox and trial accounts cap sessions far below the contracted 1800 s. The
    body is only pattern-matched here; it is never logged (it may echo the request).
    """
    if response.status_code != 400:
        return None
    match = _DURATION_CAP_RE.search(response.text[:2000])
    return int(match.group(1)) if match else None


class LiveAvatarVendor:
    """REST surface: token minting, session start/stop, keep-alive, preflight."""

    def __init__(
        self,
        settings: LiveAvatarSettings,
        *,
        api_key: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._base_url = settings.base_url.rstrip("/")
        self._api_key = api_key
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0))

    async def aclose(self) -> None:
        await self._http.aclose()

    async def create_session(self) -> VendorSession:
        body: dict[str, Any] = {
            "mode": "LITE",
            "avatar_id": self._settings.avatar_id,
            "is_sandbox": self._settings.is_sandbox,
            "max_session_duration": self._settings.max_session_duration_s,
        }
        if self._settings.voice_id:
            body["voice_id"] = self._settings.voice_id

        try:
            token_response = await self._post(
                "/v1/sessions/token",
                headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
                json=body,
                op="create_session_token",
            )
        except LiveAvatarError as exc:
            cap = exc.duration_cap_s
            if cap is None or cap >= int(body["max_session_duration"]):
                raise
            # The account's cap is below what we asked for: honour it once and
            # move on. Sessions are re-minted on expiry by the broker anyway.
            log.warning(
                "avatar.session_duration_capped",
                requested_s=body["max_session_duration"],
                vendor_cap_s=cap,
            )
            body["max_session_duration"] = cap
            token_response = await self._post(
                "/v1/sessions/token",
                headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
                json=body,
                op="create_session_token",
            )
        token_data = token_response.json().get("data") or {}
        session_token = token_data.get("session_token")
        if not session_token:
            raise LiveAvatarError("create_session_token returned no session_token")

        start_response = await self._post(
            "/v1/sessions/start",
            headers={
                "Authorization": f"Bearer {session_token}",
                "Content-Type": "application/json",
            },
            json={},
            op="start_session",
        )
        start = start_response.json().get("data") or {}
        for required in ("session_id", "livekit_url", "livekit_client_token", "ws_url"):
            if not start.get(required):
                raise LiveAvatarError(f"start_session response missing {required}")

        log.info("avatar.session_started", vendor_session_id=start["session_id"])
        return VendorSession(
            session_id=str(start["session_id"]),
            session_token=str(session_token),
            livekit_url=str(start["livekit_url"]),
            livekit_client_token=str(start["livekit_client_token"]),
            livekit_agent_token=str(start.get("livekit_agent_token", "")),
            ws_url=str(start["ws_url"]),
            max_session_duration_s=int(
                start.get("max_session_duration", self._settings.max_session_duration_s)
            ),
        )

    async def stop_session(self, session: VendorSession) -> None:
        with contextlib.suppress(httpx.HTTPError, LiveAvatarError):
            await self._post(
                "/v1/sessions/stop",
                headers={"Authorization": f"Bearer {session.session_token}"},
                json={},
                op="stop_session",
            )
        log.info("avatar.session_stopped", vendor_session_id=session.session_id)

    async def keep_alive(self, session: VendorSession) -> None:
        with contextlib.suppress(httpx.HTTPError, LiveAvatarError):
            await self._post(
                "/v1/sessions/keep-alive",
                headers={"Authorization": f"Bearer {session.session_token}"},
                json={},
                op="keep_alive",
            )

    def control_channel(self, session: VendorSession) -> AvatarControlChannel:
        return AvatarControlChannel(
            session,
            chunk_ms=self._settings.audio_chunk_ms,
            keep_alive_interval_s=self._settings.keep_alive_interval_s,
            speak_started_timeout_s=self._settings.speak_started_timeout_s,
        )

    async def preflight(self) -> tuple[bool, float | None]:
        started = time.perf_counter()
        try:
            response = await self._http.get(self._base_url + "/", timeout=3.0)
        except httpx.HTTPError:
            return False, None
        rtt_ms = (time.perf_counter() - started) * 1000
        return response.status_code < 500, round(rtt_ms, 1)

    async def _post(
        self, path: str, *, headers: dict[str, str], json: dict[str, Any], op: str
    ) -> httpx.Response:
        attempts = 0
        while True:
            attempts += 1
            try:
                response = await self._http.post(self._base_url + path, headers=headers, json=json)
            except httpx.TransportError as exc:
                if attempts >= 2:
                    raise LiveAvatarError(f"{op} transport failure") from exc
                await asyncio.sleep(0.3 * attempts)
                continue
            if response.is_success:
                return response
            # Never log the response body: it may echo the request, which carries the key.
            log.error("avatar.api_error", op=op, status=response.status_code)
            raise LiveAvatarError(
                f"{op} failed with HTTP {response.status_code}",
                status=response.status_code,
                duration_cap_s=_duration_cap(response),
            )


class AvatarControlChannel:
    """The persistent WebSocket that drives the avatar.

    Owns the audio framing contract and the avatar state machine. Commands are
    sent only after ``session.state_updated: connected`` and strictly in order.
    """

    def __init__(
        self,
        session: VendorSession,
        *,
        chunk_ms: int = 1000,
        keep_alive_interval_s: int = 240,
        speak_started_timeout_s: float = 2.0,
    ) -> None:
        self._session = session
        self._chunk_bytes = chunk_bytes_for(chunk_ms)
        self._keep_alive_interval = keep_alive_interval_s
        self._speak_started_timeout = speak_started_timeout_s
        self._ws: Any = None
        self._state = SessionState.CONNECTING
        self._avatar_state = AvatarState.IDLE
        self._ready = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()
        self._buffer = bytearray()
        self._send_lock = asyncio.Lock()
        self._speaking_bytes = 0
        self._first_speak_at: float | None = None
        self._first_frame_ms: float | None = None
        self._pending_started: dict[str, float] = {}
        self._speak_started_event = asyncio.Event()

    async def open(self) -> None:
        self._ws = await websockets.connect(
            self._session.ws_url, ping_interval=20, ping_timeout=10, max_queue=64
        )
        self._spawn(self._receive_loop())
        self._spawn(self._keep_alive_loop())
        await asyncio.wait_for(self._ready.wait(), timeout=10)

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
        self._state = SessionState.CLOSED
        self._ready.clear()

    # ── Outbound commands ────────────────────────────────────────────────────

    async def speak(self, pcm: bytes, *, flush: bool = False) -> str:
        self._buffer.extend(pcm)
        event_id = ""
        while len(self._buffer) >= self._chunk_bytes:
            chunk = bytes(self._buffer[: self._chunk_bytes])
            del self._buffer[: self._chunk_bytes]
            event_id = await self._send_audio(chunk)
        if flush and self._buffer:
            event_id = await self._send_audio(bytes(self._buffer))
            self._buffer.clear()
        return event_id

    async def speak_end(self, event_id: str) -> None:
        await self._send({"type": "agent.speak_end", "event_id": event_id})

    async def interrupt(self) -> None:
        self._buffer.clear()
        self._pending_started.clear()
        await self._send({"type": "agent.interrupt"})
        self._avatar_state = AvatarState.LISTENING

    async def start_listening(self) -> None:
        await self._send({"type": "agent.start_listening", "event_id": _new_event_id()})
        self._avatar_state = AvatarState.LISTENING

    async def stop_listening(self) -> None:
        await self._send({"type": "agent.stop_listening", "event_id": _new_event_id()})
        self._avatar_state = AvatarState.IDLE

    async def keep_alive(self) -> None:
        await self._send({"type": "session.keep_alive", "event_id": _new_event_id()})

    async def _send_audio(self, chunk: bytes) -> str:
        if len(chunk) > MAX_PACKET_BYTES or not looks_like_pcm16(chunk):
            raise LiveAvatarError("audio chunk violates the vendor contract")
        event_id = _new_event_id()
        message = {
            "type": "agent.speak",
            "audio": base64.b64encode(chunk).decode("ascii"),
            "event_id": event_id,
        }
        if self._first_speak_at is None:
            self._first_speak_at = time.perf_counter()
        self._pending_started[event_id] = time.perf_counter()
        self._speak_started_event.clear()
        await self._send(message)
        self._speaking_bytes += len(chunk)
        self._avatar_state = AvatarState.SPEAKING
        self._spawn(self._watch_speak_started(event_id, message))
        return event_id

    async def _watch_speak_started(self, event_id: str, message: dict[str, Any]) -> None:
        """Re-send once if the vendor does not acknowledge within the timeout, then degrade."""
        try:
            await asyncio.wait_for(self._speak_started_event.wait(), self._speak_started_timeout)
        except TimeoutError:
            if event_id in self._pending_started:
                log.warning("avatar.speak_not_acknowledged", event_id=event_id)
                with contextlib.suppress(LiveAvatarError):
                    await self._send(message)

    async def _send(self, message: dict[str, Any]) -> None:
        if self._ws is None or self._state is not SessionState.CONNECTED:
            raise LiveAvatarError(f"channel not connected (state={self._state})")
        async with self._send_lock:
            await self._ws.send(json.dumps(message))

    # ── Inbound events ───────────────────────────────────────────────────────

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                match event.get("type"):
                    case "session.state_updated":
                        self._state = SessionState(event.get("state", "closed"))
                        if self._state is SessionState.CONNECTED:
                            self._ready.set()
                        elif self._state in (SessionState.CLOSED, SessionState.CLOSING):
                            self._ready.clear()
                        log.info("avatar.state", state=str(self._state))
                    case "agent.speak_started" | "agent.audio_buffer_appended" | "agent.audio_buffer_committed":
                        self._avatar_state = AvatarState.SPEAKING
                        self._speak_started_event.set()
                        self._pending_started.pop(str(event.get("event_id", "")), None)
                        if self._first_frame_ms is None and self._first_speak_at is not None:
                            self._first_frame_ms = (
                                time.perf_counter() - self._first_speak_at
                            ) * 1000
                    case "agent.speak_ended" | "agent.idle_started":
                        self._avatar_state = AvatarState.IDLE
                    case _:
                        log.debug("avatar.unhandled_event", type=event.get("type"))
        except websockets.ConnectionClosed:
            self._state = SessionState.CLOSED
            self._ready.clear()
            log.warning("avatar.ws_closed", vendor_session_id=self._session.session_id)

    async def _keep_alive_loop(self) -> None:
        while True:
            await asyncio.sleep(self._keep_alive_interval)
            with contextlib.suppress(LiveAvatarError, websockets.ConnectionClosed):
                await self.keep_alive()

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @property
    def avatar_state(self) -> AvatarState:
        return self._avatar_state

    @property
    def connected(self) -> bool:
        return self._state is SessionState.CONNECTED

    @property
    def speaking_seconds(self) -> float:
        return self._speaking_bytes / 48_000

    @property
    def first_frame_ms(self) -> float | None:
        return self._first_frame_ms


def _new_event_id() -> str:
    return uuid.uuid4().hex
