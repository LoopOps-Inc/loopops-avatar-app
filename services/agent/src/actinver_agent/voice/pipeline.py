"""Cascaded voice pipeline: agent turn events → per-sentence guard → TTS → avatar
(ADR-0002, docs/01-architecture/05 §4).

Latency to first audio is a function of the first *sentence*, not the whole
answer: every approved sentence is synthesised and pushed immediately. The
output guardrail runs on each sentence before synthesis (control AI-04); a
sentence that fails is dropped - dropping is always safe, emitting is not.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from actinver_agent.avatar.broker import ActiveSession, AvatarBroker
from actinver_agent.graph.events import TurnEvent
from actinver_agent.graph.state import GuardrailAction, Intent
from actinver_agent.observability.setup import get_metrics
from actinver_agent.ports import GuardrailPort, OutputCheckRequest, TextToSpeechPort

log = structlog.get_logger(__name__)

Sender = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class VoiceTurnResult:
    approved_sentences: list[str] = field(default_factory=list)
    dropped_sentences: int = 0
    first_audio_ms: float | None = None
    filler_emitted: bool = False
    turn_id: str | None = None
    evidence_id: str | None = None
    timed_out: bool = False
    error: dict[str, Any] | None = None


class VoiceTurnPipeline:
    def __init__(
        self,
        *,
        tts: TextToSpeechPort,
        guardrail: GuardrailPort,
        broker: AvatarBroker,
        session: ActiveSession,
        send: Sender,
        filler_threshold_ms: int = 400,
        thinking_ceiling_s: float = 8.0,
        locale: str = "es-MX",
        register: str = "tu",
    ) -> None:
        self._tts = tts
        self._guardrail = guardrail
        self._broker = broker
        self._session = session
        self._send = send
        self._filler_threshold_ms = filler_threshold_ms
        self._thinking_ceiling_s = thinking_ceiling_s
        self._locale = locale
        self._register = register

    async def run(self, events: AsyncIterator[TurnEvent]) -> VoiceTurnResult:
        result = VoiceTurnResult()
        started = time.perf_counter()
        first_audio = asyncio.Event()
        speaking_announced = False
        last_event_id = ""
        intent: Intent | None = None

        await self._send({"type": "agent.thinking"})
        filler_task = asyncio.create_task(self._maybe_filler(started, first_audio, result))
        ceiling_task = asyncio.create_task(self._ceiling(first_audio))
        consumer = asyncio.create_task(self._drain(events))

        try:
            while True:
                done, _ = await asyncio.wait(
                    {consumer, ceiling_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if ceiling_task in done and not consumer.done():
                    consumer.cancel()
                    result.timed_out = True
                    await self._apologise(result)
                    break
                event: TurnEvent | None = None
                if consumer in done:
                    event = consumer.result()
                    if event is None:
                        break
                    consumer = asyncio.create_task(self._drain(events))
                if event is None:
                    continue

                if event.kind == "token":
                    sentence = str(event.data.get("text", "")).strip()
                    if not sentence:
                        continue
                    log.info(
                        "voice.sentence_timing",
                        stage="token",
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
                        chars=len(sentence),
                    )
                    if intent is None and event.data.get("intent"):
                        with contextlib.suppress(ValueError):
                            intent = Intent(str(event.data["intent"]))
                    verdict = await self._guardrail.check_output(
                        OutputCheckRequest(
                            speech=sentence,
                            intent=intent,
                            locale=self._locale,
                            register=self._register,
                            provenance_keys=frozenset(event.data.get("provenance_keys", ())),
                            stripped_product_terms=tuple(
                                event.data.get("stripped_product_terms", ())
                            ),
                            rewrite_attempts=0,
                            max_rewrite_attempts=0,
                            sentence_mode=True,
                        )
                    )
                    log.info(
                        "voice.sentence_timing",
                        stage="guardrail",
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
                        action=verdict.action.value,
                    )
                    if verdict.action is not GuardrailAction.PASS:
                        result.dropped_sentences += 1
                        log.warning("voice.sentence_blocked", violations=verdict.violations)
                        get_metrics().guardrail_blocks.add(1, {"stage": "voice_sentence"})
                        continue
                    if not speaking_announced:
                        speaking_announced = True
                        await self._send({"type": "agent.speaking"})
                    await self._send({"type": "caption", "text": sentence})
                    result.approved_sentences.append(sentence)
                    async for pcm in self._tts.synthesize_stream(sentence):
                        event_id = await self._session.channel.speak(pcm, flush=False)
                        if event_id:
                            last_event_id = event_id
                    log.info(
                        "voice.sentence_timing",
                        stage="tts_speak",
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
                    )
                    flushed = await self._session.channel.speak(b"", flush=True)
                    last_event_id = flushed or last_event_id
                    self._session.touch_avatar()
                    if not first_audio.is_set():
                        first_audio.set()
                        result.first_audio_ms = (time.perf_counter() - started) * 1000
                        get_metrics().turn_latency_first_audio_ms.record(result.first_audio_ms)
                elif event.kind == "ui":
                    # The component carries its own ``type``; wrap it so the
                    # socket envelope keeps ``type: "ui"``.
                    await self._send({"type": "ui", "component": event.data})
                elif event.kind in ("form_spec", "citations"):
                    await self._send({"type": event.kind, **event.data})
                elif event.kind == "error":
                    result.error = dict(event.data)
                    await self._send({"type": "error", **event.data})
                elif event.kind == "done":
                    result.turn_id = event.data.get("turn_id")
                    result.evidence_id = event.data.get("evidence_id")
                    first_audio.set()
                elif event.kind in ("thinking", "filler"):
                    continue
        finally:
            filler_task.cancel()
            ceiling_task.cancel()
            if not consumer.done():
                consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.gather(filler_task, ceiling_task, return_exceptions=True)

        if last_event_id and not self._session.ended:
            with contextlib.suppress(Exception):
                await self._session.channel.speak_end(last_event_id)
        if not self._session.ended:
            with contextlib.suppress(Exception):
                await self._session.channel.start_listening()

        await self._send(
            {
                "type": "turn.complete",
                "turn_id": result.turn_id,
                "evidence_id": result.evidence_id,
                "timed_out": result.timed_out,
            }
        )
        get_metrics().turn_total_ms.record(
            (time.perf_counter() - started) * 1000, {"channel": "voice"}
        )
        log.info(
            "voice.turn_complete",
            first_audio_ms=round(result.first_audio_ms or -1, 1),
            total_ms=round((time.perf_counter() - started) * 1000, 1),
            sentences=len(result.approved_sentences),
            dropped=result.dropped_sentences,
            timed_out=result.timed_out,
        )
        return result

    @staticmethod
    async def _drain(events: AsyncIterator[TurnEvent]) -> TurnEvent | None:
        try:
            return await events.__anext__()
        except StopAsyncIteration:
            return None

    async def _maybe_filler(
        self, started: float, first_audio: asyncio.Event, result: VoiceTurnResult
    ) -> None:
        """Cover tool latency with a pre-synthesised acknowledgement (400 ms)."""
        await asyncio.sleep(self._filler_threshold_ms / 1000)
        if first_audio.is_set() or self._broker_fillers() is None:
            return
        text, pcm = self._broker_fillers().next_filler()
        result.filler_emitted = True
        await self._send({"type": "filler", "text": text})
        await self._broker.speak_system(self._session, text, pcm)
        log.info(
            "voice.filler_emitted", elapsed_ms=round((time.perf_counter() - started) * 1000, 1)
        )

    def _broker_fillers(self) -> Any:
        return getattr(self._broker, "_fillers", None)

    async def _ceiling(self, first_audio: asyncio.Event) -> None:
        """THINKING has a hard ceiling; beyond it the agent apologises (docs/01-architecture/05 §5)."""
        await asyncio.sleep(self._thinking_ceiling_s)
        if first_audio.is_set():
            await asyncio.Event().wait()  # never completes; the consumer wins the race

    async def _apologise(self, result: VoiceTurnResult) -> None:
        fillers = self._broker_fillers()
        text, pcm = (
            fillers.apology()
            if fillers is not None
            else (
                "Disculpa, esto me está tomando más de lo esperado. Te comunico con tu asesor.",
                b"",
            )
        )
        await self._send(
            {"type": "error", "code": "THINKING_TIMEOUT", "message": text, "escalate": True}
        )
        await self._send(
            {
                "type": "ui",
                "component": {
                    "type": "escalation_offer",
                    "payload": {"reason": "THINKING_TIMEOUT", "cta_es": "Hablar con mi asesor"},
                    "source": "system",
                    "as_of": None,
                },
            }
        )
        await self._send({"type": "caption", "text": text})
        await self._broker.speak_system(self._session, text, pcm)
        result.error = {"code": "THINKING_TIMEOUT", "message": text, "escalate": True}
