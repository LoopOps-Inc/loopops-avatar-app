"""``WS /v1/avatar/{session_id}/audio`` - the bidirectional audio path
(docs/04-backend/04 §2, docs/01-architecture/03 §2).

Client → server
  binary frame                       microphone audio (Opus/WebM chunks from the web client)
  {"type":"auth","token":"..."}      first message when the token cannot travel in a header
  {"type":"audio_start","mime":"audio/webm;codecs=opus"}
  {"type":"utterance_end"}
  {"type":"client.barge_in","at":<epoch_ms>}
  {"type":"client.ready","has_video":true,"has_audio":true}   after LiveKit tracks are subscribed
  {"type":"client.speak","text":"..."}           chat-mode speech bridge (TTS + lip-sync)
  {"type":"client.background"} / {"type":"client.foreground"}
  {"type":"dev.transcript","text":"...","confidence":0.94}   dev-only (VOICE_PROVIDER=stub)

Server → client
  {"type":"transcript.partial","text"}          {"type":"transcript.final","text","confidence"}
  {"type":"agent.thinking"}                     {"type":"agent.speaking"}
  {"type":"filler","text"}                      {"type":"caption","text"}   (mandatory captions)
  {"type":"ui","component":{...UIComponent}}    {"type":"form_spec",...}    {"type":"citations","items":[...]}
  {"type":"error","code","message","escalate"}  {"type":"turn.complete","turn_id","evidence_id"}
  {"type":"session.refreshed","livekit_url","livekit_client_token"}   {"type":"session.expiring"}
  {"type":"session.closed","reason"}

Close codes: 4401 unauthenticated · 4403 not the session owner · 4404 unknown/ended session.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import orjson
import structlog
from fastapi import WebSocket, WebSocketDisconnect

from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import authenticate
from actinver_agent.avatar.broker import ActiveSession, AvatarBroker
from actinver_agent.deps import Dependencies
from actinver_agent.errors import ApiError
from actinver_agent.observability.setup import get_metrics
from actinver_agent.ports import SpeechToTextPort, Transcript
from actinver_agent.voice.pipeline import VoiceTurnPipeline
from actinver_agent.voice.segmentation import split_sentences
from actinver_agent.voice.stub import StubSpeechToText

log = structlog.get_logger(__name__)

CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404


class _Utterance:
    """Audio and transcript state for one client utterance."""

    def __init__(self) -> None:
        self.frames: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.audio = bytearray()
        self.onset: float | None = None
        self.partial: str = ""
        self.mime: str = "audio/opus"

    async def stream(self) -> AsyncIterator[bytes]:
        while True:
            frame = await self.frames.get()
            if frame is None:
                return
            yield frame


class AudioSocketHandler:
    def __init__(self, deps: Dependencies, broker: AvatarBroker) -> None:
        self._deps = deps
        self._broker = broker

    async def handle(self, websocket: WebSocket, avatar_session_id: str) -> None:
        await websocket.accept()
        ctx = await self._authenticate(websocket)
        if ctx is None:
            await websocket.close(code=CLOSE_UNAUTHENTICATED)
            return
        session = self._broker.get(avatar_session_id)
        if session is None or session.ended:
            await self._send(
                websocket,
                {
                    "type": "error",
                    "code": "SESSION_NOT_FOUND",
                    "message": "La sesión de voz ya terminó.",
                },
            )
            await websocket.close(code=CLOSE_NOT_FOUND)
            return
        if session.client_id != ctx.client_id:
            log.warning(
                "voice.ws_forbidden",
                avatar_session_id=avatar_session_id,
                session_client=session.client_id,
                token_client=ctx.client_id,
            )
            await websocket.close(code=CLOSE_FORBIDDEN)
            return

        session.notifier = lambda message: self._send(websocket, message)
        session.touch_client()
        log.info("voice.ws_connected", avatar_session_id=avatar_session_id)

        stt = self._stt_for_connection()
        utterance = _Utterance()
        stt_task = asyncio.create_task(self._transcribe(websocket, session, ctx, stt, utterance))
        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    if stt_task.done():
                        utterance = _Utterance()
                        stt_task = asyncio.create_task(
                            self._transcribe(websocket, session, ctx, stt, utterance)
                        )
                    self._on_audio(session, utterance, message["bytes"])
                    continue
                text = message.get("text")
                if not text:
                    continue
                try:
                    payload = orjson.loads(text)
                except orjson.JSONDecodeError:
                    continue
                utterance, stt_task = await self._on_control(
                    websocket, session, ctx, stt, utterance, stt_task, payload
                )
        except WebSocketDisconnect:
            pass
        finally:
            session.notifier = None
            stt_task.cancel()
            utterance.frames.put_nowait(None)
            if isinstance(stt, StubSpeechToText):
                stt.close()
            # Every path out of voice mode tears the session down after the grace.
            if not session.ended:
                self._broker.background_grace(avatar_session_id)

    # ── Auth ────────────────────────────────────────────────────────────────

    async def _authenticate(self, websocket: WebSocket) -> RequestContext | None:
        token = websocket.query_params.get("access_token")
        authorization = websocket.headers.get("authorization")
        if token is None and authorization is None:
            try:
                first = await asyncio.wait_for(websocket.receive_text(), timeout=5)
                payload = orjson.loads(first)
                if payload.get("type") == "auth":
                    token = str(payload.get("token", ""))
            except (TimeoutError, orjson.JSONDecodeError, WebSocketDisconnect):
                return None
        # Browsers cannot set WebSocket headers. Docker nginx injects a default
        # Authorization when the header is empty, which would shadow the
        # investor JWT the client put in ?access_token=. Prefer the query token.
        header = (f"Bearer {token}" if token else None) or authorization
        try:
            # The access token was DPoP-bound when the avatar session was created;
            # browsers cannot attach a proof to the WebSocket handshake, so the
            # socket relies on the session ownership check below plus the token.
            return await authenticate(
                self._deps,
                authorization=header,
                dpop=websocket.headers.get("dpop"),
                method="GET",
                url=str(websocket.url),
            )
        except ApiError as exc:
            log.warning("voice.ws_auth_failed", reason=exc.detail)
            return None

    def _stt_for_connection(self) -> SpeechToTextPort:
        if self._deps.settings.voice.provider == "stub":
            return StubSpeechToText(language=self._deps.settings.voice.stt_language)
        return self._deps.stt

    # ── Inbound ─────────────────────────────────────────────────────────────

    def _on_audio(self, session: ActiveSession, utterance: _Utterance, frame: bytes) -> None:
        if utterance.onset is None:
            utterance.onset = time.monotonic()
        utterance.audio.extend(frame)
        utterance.frames.put_nowait(frame)
        session.touch_client()

    async def _on_control(
        self,
        websocket: WebSocket,
        session: ActiveSession,
        ctx: RequestContext,
        stt: SpeechToTextPort,
        utterance: _Utterance,
        stt_task: asyncio.Task[None],
        payload: dict[str, Any],
    ) -> tuple[_Utterance, asyncio.Task[None]]:
        kind = payload.get("type")
        match kind:
            case "audio_start":
                utterance.mime = str(payload.get("mime", "audio/opus"))[:60]
                utterance.onset = time.monotonic()
                session.touch_client()
            case "utterance_end":
                utterance.frames.put_nowait(None)
                session.touch_client()
            case "client.barge_in":
                await self._barge_in(session, utterance)
            case "client.background":
                self._broker.background_grace(session.avatar_session_id)
            case "client.foreground":
                self._broker.cancel_background_grace(session.avatar_session_id)
            case "client.ready":
                session.touch_client()
                log.info(
                    "voice.client_ready",
                    avatar_session_id=session.avatar_session_id,
                    has_video=bool(payload.get("has_video")),
                    has_audio=bool(payload.get("has_audio")),
                )
                await self._maybe_greet(session)
            case "client.speak":
                text = str(payload.get("text", "")).strip()
                if text:
                    session.touch_client()
                    await self._speak_caption(session, text)
            case "dev.transcript":
                if self._deps.settings.voice.provider != "stub" or not isinstance(
                    stt, StubSpeechToText
                ):
                    await self._send(
                        websocket,
                        {
                            "type": "error",
                            "code": "NOT_ALLOWED",
                            "message": "dev.transcript solo está disponible en modo stub.",
                        },
                    )
                else:
                    stt.push_text(
                        str(payload.get("text", "")), float(payload.get("confidence", 0.95))
                    )
                    utterance.frames.put_nowait(None)
            case "auth":
                pass
            case _:
                log.debug("voice.unknown_message", kind=str(kind))
        if utterance.frames.empty() and stt_task.done():
            utterance = _Utterance()
            stt_task = asyncio.create_task(
                self._transcribe(websocket, session, ctx, stt, utterance)
            )
        return utterance, stt_task

    async def _maybe_greet(self, session: ActiveSession) -> None:
        """Greet once the browser has subscribed to LiveKit A/V (avoids speaking into the void)."""
        if session.greeted:
            return
        session.greeted = True
        log.info("avatar.greeting", avatar_session_id=session.avatar_session_id)
        await self._broker.greet(session)

    async def _speak_caption(self, session: ActiveSession, text: str) -> None:
        """Synthesize *text* per sentence so the first clip starts before the rest."""
        log.info(
            "voice.client_speak",
            avatar_session_id=session.avatar_session_id,
            text_len=len(text),
        )
        for sentence in split_sentences(text):
            started = time.monotonic()
            pcm = b"".join([chunk async for chunk in self._deps.tts.synthesize_stream(sentence)])
            log.info(
                "voice.client_speak_synth",
                avatar_session_id=session.avatar_session_id,
                pcm_bytes=len(pcm),
                text_len=len(sentence),
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
            await self._broker.speak_system(session, sentence, pcm, notify_caption=False)

    async def _barge_in(self, session: ActiveSession, utterance: _Utterance) -> None:
        get_metrics().barge_ins.add(1)
        cancelled = session.cancel_turn()
        with contextlib.suppress(Exception):
            await session.channel.interrupt()
        session.touch_client()
        window = self._deps.settings.voice.stutter_restart_window_s
        if utterance.onset is not None and time.monotonic() - utterance.onset > window:
            # Not a stutter/restart: discard the partial transcript and log.
            utterance.partial = ""
        log.info("voice.barge_in", cancelled_turn=cancelled)

    # ── Transcription and turn execution ─────────────────────────────────────

    async def _transcribe(
        self,
        websocket: WebSocket,
        session: ActiveSession,
        ctx: RequestContext,
        stt: SpeechToTextPort,
        utterance: _Utterance,
    ) -> None:
        try:
            async for transcript in stt.stream(utterance.stream()):
                if not transcript.is_final:
                    utterance.partial = transcript.text
                    await self._send(
                        websocket, {"type": "transcript.partial", "text": transcript.text}
                    )
                    continue
                await self._on_final(websocket, session, ctx, utterance, transcript)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("voice.stt_failed", reason=type(exc).__name__)
            await self._send(
                websocket,
                {
                    "type": "error",
                    "code": "LOW_CONFIDENCE",
                    "message": "No te escuché bien. ¿Me lo repites, por favor?",
                    "escalate": False,
                },
            )

    async def _on_final(
        self,
        websocket: WebSocket,
        session: ActiveSession,
        ctx: RequestContext,
        utterance: _Utterance,
        transcript: Transcript,
    ) -> None:
        text = transcript.text.strip()
        if utterance.partial and not text.startswith(utterance.partial):
            text = f"{utterance.partial} {text}".strip()
        utterance.partial = ""
        get_metrics().asr_confidence.record(transcript.confidence)
        await self._send(
            websocket,
            {"type": "transcript.final", "text": text, "confidence": transcript.confidence},
        )
        if not text:
            return
        audio_ref = await self._store_audio(session, utterance)
        utterance.audio.clear()
        utterance.onset = None

        runner = self._deps.runner
        if runner is None:
            await self._send(
                websocket,
                {
                    "type": "error",
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "El asistente no está disponible.",
                    "escalate": True,
                },
            )
            return
        events = runner.run_turn(
            ctx,
            thread_id=session.thread_id,
            text=text,
            channel="voice",
            transcript_confidence=transcript.confidence,
            audio_ref=audio_ref,
            locale=ctx.locale,
        )
        pipeline = VoiceTurnPipeline(
            tts=self._deps.tts,
            guardrail=self._deps.guardrail,
            broker=self._broker,
            session=session,
            send=lambda message: self._send(websocket, message),
            filler_threshold_ms=self._deps.settings.voice.filler_threshold_ms,
            thinking_ceiling_s=self._deps.settings.voice.thinking_ceiling_s,
            locale=ctx.locale,
        )
        turn = asyncio.create_task(pipeline.run(events))
        session.current_turn = turn
        try:
            await turn
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise  # the socket itself is going away
            log.info("voice.turn_cancelled")  # barge-in cancelled the turn only
        finally:
            session.current_turn = None

    async def _store_audio(self, session: ActiveSession, utterance: _Utterance) -> str | None:
        """Client audio is a DCGSI Art. 26 record: WORM, tied to the consent version (IS-10)."""
        if not utterance.audio:
            return None
        now = datetime.now(UTC)
        segment_id = f"seg_{uuid.uuid4().hex[:12]}"
        key = f"audio/{now:%Y/%m}/{session.thread_id}/{segment_id}.opus"
        retain_until = now + timedelta(days=365 * self._deps.settings.object_store.retention_years)
        try:
            await self._deps.object_store.put_immutable(
                key, bytes(utterance.audio), retain_until=retain_until, content_type=utterance.mime
            )
            await self._deps.repos.audio_segments.record(
                thread_id=session.thread_id,
                turn_id="pending",
                segment_id=segment_id,
                object_key=key,
                speaker="client",
                consent_version=session.consent_version,
                created_at=now,
            )
        except Exception as exc:
            log.error("voice.audio_store_failed", reason=type(exc).__name__)
            return None
        return key

    @staticmethod
    async def _send(websocket: WebSocket, message: dict[str, Any]) -> None:
        with contextlib.suppress(Exception):
            await websocket.send_text(orjson.dumps(message, default=str).decode())
