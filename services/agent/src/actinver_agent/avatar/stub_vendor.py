"""Emulated LiveAvatar vendor for local development and CI.

Implements the same ports as the real client so the broker, framing, timers
and state machine run end to end without credits or credentials.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from actinver_agent.ports import VendorSession
from actinver_agent.voice.framing import BYTES_PER_SECOND


@dataclass
class StubControlChannel:
    session: VendorSession
    sent: list[dict[str, Any]] = field(default_factory=list)
    _connected: bool = False
    _speaking_bytes: int = 0
    _first_speak_at: float | None = None
    _first_frame_ms: float | None = None
    _buffer: bytearray = field(default_factory=bytearray)
    chunk_bytes: int = BYTES_PER_SECOND
    interrupts: int = 0

    async def open(self) -> None:
        await asyncio.sleep(0)
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def speak(self, pcm: bytes, *, flush: bool = False) -> str:
        if not self._connected:
            raise RuntimeError("channel not connected")
        self._buffer.extend(pcm)
        event_id = ""
        while len(self._buffer) >= self.chunk_bytes:
            event_id = self._send_audio(bytes(self._buffer[: self.chunk_bytes]))
            del self._buffer[: self.chunk_bytes]
        if flush and self._buffer:
            event_id = self._send_audio(bytes(self._buffer))
            self._buffer.clear()
        return event_id

    def _send_audio(self, chunk: bytes) -> str:
        event_id = secrets.token_hex(8)
        if self._first_speak_at is None:
            self._first_speak_at = time.perf_counter()
            self._first_frame_ms = 120.0
        self._speaking_bytes += len(chunk)
        self.sent.append({"type": "agent.speak", "bytes": len(chunk), "event_id": event_id})
        return event_id

    async def speak_end(self, event_id: str) -> None:
        self.sent.append({"type": "agent.speak_end", "event_id": event_id})

    async def interrupt(self) -> None:
        self._buffer.clear()
        self.interrupts += 1
        self.sent.append({"type": "agent.interrupt"})

    async def start_listening(self) -> None:
        self.sent.append({"type": "agent.start_listening"})

    async def stop_listening(self) -> None:
        self.sent.append({"type": "agent.stop_listening"})

    async def keep_alive(self) -> None:
        self.sent.append({"type": "session.keep_alive"})

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def speaking_seconds(self) -> float:
        return self._speaking_bytes / BYTES_PER_SECOND

    @property
    def first_frame_ms(self) -> float | None:
        return self._first_frame_ms


class StubAvatarVendor:
    def __init__(self, *, max_session_duration_s: int = 1800, fail_start: bool = False) -> None:
        self._max = max_session_duration_s
        self.fail_start = fail_start
        self.sessions: dict[str, VendorSession] = {}
        self.stopped: list[str] = []

    async def create_session(self) -> VendorSession:
        if self.fail_start:
            raise RuntimeError("stub vendor configured to fail")
        session = VendorSession(
            session_id=f"stub_{secrets.token_hex(8)}",
            session_token=secrets.token_urlsafe(16),
            livekit_url="wss://stub.local/livekit",
            livekit_client_token=secrets.token_urlsafe(24),
            livekit_agent_token=secrets.token_urlsafe(24),
            ws_url="wss://stub.local/ws",
            max_session_duration_s=self._max,
        )
        self.sessions[session.session_id] = session
        return session

    async def stop_session(self, session: VendorSession) -> None:
        self.stopped.append(session.session_id)
        self.sessions.pop(session.session_id, None)

    async def keep_alive(self, session: VendorSession) -> None:  # noqa: ARG002
        return None

    def control_channel(self, session: VendorSession) -> StubControlChannel:
        return StubControlChannel(session=session)

    async def preflight(self) -> tuple[bool, float | None]:
        return True, 5.0
