"""TurnRunner: the boundary between the API/voice layers and the graph.

Builds the initial state from the *validated request context* (``client_id``
comes from the token and nowhere else), runs the graph under a hard ceiling,
turns the final state into the ordered event stream both transports consume,
persists the turn, and handles suspension/resumption of transactional forms.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import orjson
import structlog
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from actinver_agent.auth.context import RequestContext
from actinver_agent.deps import Dependencies
from actinver_agent.flags import KILL_SWITCH_MESSAGE_ES
from actinver_agent.graph.events import TurnEvent, TurnOutcome
from actinver_agent.graph.state import Entitlements
from actinver_agent.observability.setup import client_hash, get_metrics
from actinver_agent.ports import TurnRecord
from actinver_agent.voice.segmentation import SentenceSplitter

log = structlog.get_logger(__name__)

CORE_DOWN_ES = (
    "No puedo consultar tu información en este momento. Prefiero no darte datos que no "
    "pueda confirmar; te comunico con tu asesor."
)
TURN_TIMEOUT_ES = (
    "Me está tomando más de lo esperado. Te comunico con tu asesor para que te atienda sin esperar."
)

#: Per-turn fields reset at the start of every run so nothing leaks from the
#: previous turn's checkpoint (``messages`` accumulates by design).
_TURN_RESET: dict[str, Any] = {
    "transcript_confidence": None,
    "audio_ref": None,
    "intent": None,
    "intent_confidence": 0.0,
    "intent_runner_up": None,
    "service_type": "no_asesorado",
    "service_subtype": "informacion",
    "degraded_from": None,
    "profile_filtered": False,
    "investor_profile": None,
    "tool_results": {},
    "provenance": {},
    "candidate_products": [],
    "proposed_amount": None,
    "tool_rounds": 0,
    "tool_calls_made": 0,
    "planned_calls": [],
    "needs_more_tools": False,
    "stripped_products": [],
    "suitability": None,
    "guardrail_input": None,
    "guardrail_output": None,
    "rewrite_attempts": 0,
    "speech": None,
    "ui_payload": [],
    "citations": [],
    "form_spec": None,
    "disclosures_shown": {},
    "disclosure_texts": {},
    "model_meta": {},
    "submission": None,
    "receipt": None,
    "filler_emitted": False,
    "distress": False,
    "error": None,
    "evidence_id": None,
}


class TurnRunner:
    def __init__(self, deps: Dependencies) -> None:
        self._deps = deps

    # ── Public API ───────────────────────────────────────────────────────────

    async def run_turn(
        self,
        ctx: RequestContext,
        *,
        thread_id: str,
        text: str,
        channel: str = "chat",
        transcript_confidence: float | None = None,
        audio_ref: str | None = None,
        locale: str = "es-MX",
    ) -> AsyncIterator[TurnEvent]:
        deps = self._deps
        turn_id = f"tn_{uuid.uuid4().hex}"
        started = time.perf_counter()
        metrics = get_metrics()
        if channel == "voice":
            yield TurnEvent("thinking", {"turn_id": turn_id})

        if await deps.flags.kill_switch_active():
            metrics.kill_switch_refusals.add(1)
            yield TurnEvent(
                "error",
                {"code": "KILL_SWITCH", "message": KILL_SWITCH_MESSAGE_ES, "escalate": True},
            )
            yield TurnEvent(
                "ui",
                {
                    "type": "escalation_offer",
                    "source": "system",
                    "as_of": None,
                    "payload": {"reason": "KILL_SWITCH", "cta_es": "Hablar con mi asesor"},
                },
            )
            yield TurnEvent(
                "done",
                {
                    "turn_id": turn_id,
                    "evidence_id": None,
                    "service_type": "no_asesorado",
                    "intent": None,
                },
            )
            return

        await self._cancel_pending_form(thread_id)
        try:
            first_name, entitlements, register = await self._client_context(ctx.client_id)
        except Exception as exc:
            log.error("turn.client_context_unavailable", reason=type(exc).__name__)
            metrics.escalations.add(1, {"reason": "CORE_UNAVAILABLE"})
            yield TurnEvent(
                "error",
                {"code": "CORE_UNAVAILABLE", "message": CORE_DOWN_ES, "escalate": True},
            )
            yield TurnEvent(
                "ui",
                {
                    "type": "escalation_offer",
                    "source": "system",
                    "as_of": None,
                    "payload": {"reason": "CORE_UNAVAILABLE", "cta_es": "Hablar con mi asesor"},
                },
            )
            yield TurnEvent(
                "done",
                {
                    "turn_id": turn_id,
                    "evidence_id": None,
                    "service_type": "no_asesorado",
                    "intent": None,
                },
            )
            return
        state: dict[str, Any] = {
            **_TURN_RESET,
            "client_id": ctx.client_id,
            "first_name": first_name,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "channel": channel,
            "locale": locale,
            "register": register,
            "entitlements": entitlements,
            "messages": [HumanMessage(content=text)],
            "client_input_text": text,
            "transcript_confidence": transcript_confidence,
            "audio_ref": audio_ref,
            "started_at": datetime.now(UTC).isoformat(),
        }
        config = {"configurable": {"thread_id": thread_id}}
        structlog.contextvars.bind_contextvars(turn_id=turn_id, client=client_hash(ctx.client_id))

        ceiling = deps.settings.limits.turn_hard_ceiling_s
        try:
            final: dict[str, Any] = await asyncio.wait_for(
                deps.graph.ainvoke(state, config=config), timeout=ceiling
            )
        except TimeoutError:
            log.error("turn.ceiling_exceeded", ceiling_s=ceiling)
            metrics.escalations.add(1, {"reason": "TURN_TIMEOUT"})
            outcome = TurnOutcome(
                turn_id=turn_id,
                thread_id=thread_id,
                speech=TURN_TIMEOUT_ES,
                ui_payload=[
                    {
                        "type": "escalation_offer",
                        "source": "system",
                        "as_of": None,
                        "payload": {"reason": "TURN_TIMEOUT", "cta_es": "Hablar con mi asesor"},
                    }
                ],
                citations=[],
                form_spec=None,
                error={"code": "TURN_TIMEOUT", "message": TURN_TIMEOUT_ES, "escalate": True},
                evidence_id=None,
                service_type="no_asesorado",
                service_subtype="informacion",
                intent=None,
                degraded_from=None,
                disclosures_shown={},
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
        else:
            outcome = self._outcome(final, turn_id, thread_id, started)

        await self._persist(ctx, channel, text, outcome)
        metrics.turns.add(
            1,
            {
                "channel": channel,
                "service_type": outcome.service_type,
                "intent": outcome.intent or "none",
                "refused": str(outcome.error is not None),
            },
        )
        metrics.turn_total_ms.record(outcome.elapsed_ms, {"channel": channel})
        if outcome.error is not None:
            metrics.escalations.add(1, {"reason": outcome.error["code"]})

        provenance_keys = (
            sorted(final.get("provenance", {}).keys()) if outcome.error is None else []
        )
        stripped_terms = [
            t
            for p in (final.get("stripped_products", []) if outcome.error is None else [])
            for t in (p.product_id, p.name)
        ]
        for event in self._events(outcome, provenance_keys, stripped_terms):
            yield event

    async def resume_form(
        self,
        ctx: RequestContext,
        *,
        thread_id: str,
        form_id: str,
        submission: dict[str, Any],
        receipt: dict[str, Any],
    ) -> TurnOutcome:
        deps = self._deps
        config = {"configurable": {"thread_id": thread_id}}
        pending = await self.pending_form(thread_id)
        if pending != form_id:
            raise LookupError(f"no pending form {form_id} on this thread")
        started = time.perf_counter()
        final: dict[str, Any] = await asyncio.wait_for(
            deps.graph.ainvoke(
                Command(resume={"submission": submission, "receipt": receipt}), config=config
            ),
            timeout=deps.settings.limits.turn_hard_ceiling_s,
        )
        outcome = self._outcome(final, str(final.get("turn_id")), thread_id, started)
        await self._persist(
            ctx, str(final.get("channel", "chat")), "[confirmación de operación]", outcome
        )
        return outcome

    async def pending_form(self, thread_id: str) -> str | None:
        snapshot = await self._deps.graph.aget_state({"configurable": {"thread_id": thread_id}})
        for task in getattr(snapshot, "tasks", ()) or ():
            for intr in getattr(task, "interrupts", ()) or ():
                value = getattr(intr, "value", None)
                if isinstance(value, dict) and value.get("form_id"):
                    return str(value["form_id"])
        return None

    # ── Internals ────────────────────────────────────────────────────────────

    async def _cancel_pending_form(self, thread_id: str) -> None:
        """A new message while a form is pending cancels the form (expired/cancelled → end)."""
        form_id = await self.pending_form(thread_id)
        if form_id is None:
            return
        log.info("turn.pending_form_cancelled", form_id=form_id)
        try:
            await self._deps.repos.form_specs.mark(form_id, status="CANCELLED")
        except Exception:
            pass
        await self._deps.graph.ainvoke(
            Command(resume={"cancelled": True}), config={"configurable": {"thread_id": thread_id}}
        )

    async def _client_context(self, client_id: str) -> tuple[str, Entitlements, str]:
        key = f"ctx:{client_id}"
        try:
            cached = await self._deps.cache.get(key)
        except Exception:
            cached = None
        if cached:
            data = orjson.loads(cached)
        else:
            data = await self._deps.core.get_client_context(client_id=client_id)
            try:
                await self._deps.cache.set(key, orjson.dumps(data, default=str), ttl_s=300)
            except Exception:
                pass
        entitlements = Entitlements.model_validate(data.get("entitlements", {}))
        register = data.get("register", "tu")
        return (
            str(data.get("first_name", "")),
            entitlements,
            register if register in ("tu", "usted") else "tu",
        )

    def _outcome(
        self, final: dict[str, Any], turn_id: str, thread_id: str, started: float
    ) -> TurnOutcome:
        error = final.get("error")
        form = final.get("form_spec")
        intent = final.get("intent")
        degraded = final.get("degraded_from")
        return TurnOutcome(
            turn_id=turn_id,
            thread_id=thread_id,
            speech=final.get("speech"),
            ui_payload=[c.model_dump(mode="json") for c in final.get("ui_payload", [])],
            citations=[c.model_dump(mode="json") for c in final.get("citations", [])],
            form_spec=form.model_dump(mode="json")
            if form is not None and not final.get("receipt")
            else None,
            error=(
                {"code": error.code, "message": error.message_es, "escalate": error.escalate}
                if error is not None
                else None
            ),
            evidence_id=final.get("evidence_id"),
            service_type=str(final.get("service_type") or "no_asesorado"),
            service_subtype=str(final.get("service_subtype") or "informacion"),
            intent=str(intent) if intent else None,
            degraded_from=str(degraded) if degraded else None,
            disclosures_shown=dict(final.get("disclosures_shown") or {}),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )

    def _events(
        self, outcome: TurnOutcome, provenance_keys: list[str], stripped_terms: list[str]
    ) -> list[TurnEvent]:
        events: list[TurnEvent] = []
        if outcome.error is None and outcome.speech:
            for sentence in _sentences(outcome.speech):
                events.append(
                    TurnEvent(
                        "token",
                        {
                            "text": sentence,
                            "intent": outcome.intent,
                            "provenance_keys": provenance_keys,
                            "stripped_product_terms": stripped_terms,
                        },
                    )
                )
        for component in outcome.ui_payload:
            if component.get("type") == "form_spec":
                continue
            events.append(TurnEvent("ui", component))
        if outcome.form_spec is not None:
            events.append(TurnEvent("form_spec", outcome.form_spec))
        if outcome.citations:
            events.append(TurnEvent("citations", {"items": outcome.citations}))
        if outcome.error is not None:
            events.append(TurnEvent("error", outcome.error))
        events.append(
            TurnEvent(
                "done",
                {
                    "turn_id": outcome.turn_id,
                    "evidence_id": outcome.evidence_id,
                    "service_type": outcome.service_type,
                    "service_subtype": outcome.service_subtype,
                    "intent": outcome.intent,
                    "degraded_from": outcome.degraded_from,
                    "disclosures_shown": outcome.disclosures_shown,
                    "elapsed_ms": outcome.elapsed_ms,
                },
            )
        )
        return events

    async def _persist(
        self, ctx: RequestContext, channel: str, text: str, outcome: TurnOutcome
    ) -> None:
        try:
            await self._deps.repos.threads.append_turn(
                TurnRecord(
                    turn_id=outcome.turn_id,
                    thread_id=outcome.thread_id,
                    created_at=datetime.now(UTC),
                    channel=channel,
                    client_text=text,
                    speech=outcome.speech,
                    ui_payload=outcome.ui_payload,
                    evidence_id=outcome.evidence_id,
                    service_type=outcome.service_type,
                    intent=outcome.intent or "unknown",
                    error_code=outcome.error["code"] if outcome.error else None,
                )
            )
        except Exception as exc:
            log.warning(
                "turn.persist_failed", reason=type(exc).__name__, client=client_hash(ctx.client_id)
            )


def _sentences(speech: str) -> list[str]:
    splitter = SentenceSplitter()
    out = splitter.feed(speech)
    if (tail := splitter.flush()) is not None:
        out.append(tail)
    return out or [speech]
