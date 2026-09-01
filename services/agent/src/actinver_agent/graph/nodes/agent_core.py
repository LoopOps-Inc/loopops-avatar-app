"""Planning, tool execution and generation nodes (docs/01-architecture/06 §3.4-3.5).

What is load-bearing here is the *shape*: bounded rounds, bounded calls,
parallel fan-out under a total budget, provenance recording, intent-scoped tool
declarations, and untrusted retrieved content scanned before the model sees it.
The model binding itself is behind ``Planner``/``Generator`` ports.
"""

from __future__ import annotations

import asyncio
import re
import time
from decimal import Decimal
from typing import Any

import structlog

from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import (
    ADVISORY_INTENTS,
    DEEP_MODEL_INTENTS,
    TRANSACTIONAL_INTENTS,
    AdvisorState,
    AgentError,
    Intent,
    Money,
    ProductProfile,
    ProvenanceEntry,
    ToolResult,
)
from actinver_agent.llm.stub import extract_amount
from actinver_agent.observability.setup import get_metrics, node_span
from actinver_agent.tools.registry import derived_keys, record_provenance

log = structlog.get_logger(__name__)

_CLIENT_FIGURE = re.compile(
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<unit>millones|mill[oó]n|mil)?",
    re.IGNORECASE,
)

MODEL_DOWN_ES = (
    "No puedo generar una respuesta en este momento. Te comunico con tu asesor para que te atienda."
)
DEGRADATION_NOTICE_ES = (
    "NOTA: este cliente NO tiene contratado el servicio asesorado. Puedes describir "
    "productos de forma general, pero NO puedes recomendar uno para su situación "
    'particular ni decir que "le conviene". Ofrece contactar a su asesor.'
)


async def plan(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    """Ask the model which tools to call, restricted to this intent's set."""
    if state.get("error") is not None:
        return {"planned_calls": []}
    intent = str(state["intent"])
    declarations = deps.registry.declarations_for(intent)
    allowed = set(deps.registry.allowed_for(intent))
    with node_span("plan", turn_id=state.get("turn_id"), intent=intent):
        try:
            calls = await asyncio.wait_for(
                deps.planner.plan(state=state, declarations=declarations),
                timeout=deps.settings.limits.model_timeout_s,
            )
        except Exception as exc:
            log.warning("plan.failed", reason=type(exc).__name__, detail=str(exc)[:240])
            calls = []
    limit = deps.settings.limits.max_tool_calls_per_turn - state.get("tool_calls_made", 0)
    planned = [
        {"name": c.name, "args": dict(c.args)}
        for c in calls
        if c.name in allowed and c.name in deps.registry
    ][: max(limit, 0)]
    dropped = len(calls) - len(planned)
    if dropped:
        log.info("plan.calls_dropped", dropped=dropped, intent=intent)
    planned = _ensure_transactional_tools(state, planned)
    return {
        "planned_calls": planned,
        "needs_more_tools": False,
        "provenance": {**state.get("provenance", {}), **_client_input_provenance(state)},
    }


def _client_input_provenance(state: AdvisorState) -> dict[str, ProvenanceEntry]:
    """Figures the client stated ("200 mil", "3 años") are not invented: they are
    sourced from the client input and may be echoed back in speech."""
    text = state.get("client_input_text", "")
    entries: dict[str, ProvenanceEntry] = {}
    for match in _CLIENT_FIGURE.finditer(text):
        raw, unit = match.group("num"), (match.group("unit") or "").lower()
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        scale = 1_000_000 if unit.startswith("mill") else 1_000 if unit == "mil" else 1
        for figure in {value, value * scale}:
            for key in derived_keys(figure):
                entries.setdefault(
                    key, ProvenanceEntry(value=str(figure), tool="client_input", path="text")
                )
    return entries


_TRANSACT_OPERATION: dict[Intent, str] = {
    Intent.TRANSACT_BUY: "BUY",
    Intent.TRANSACT_SELL: "SELL",
    Intent.TRANSACT_SWITCH: "SWITCH",
    Intent.TRANSACT_REDEEM: "REDEEM",
}
_PRODUCT_CODE = re.compile(r"\b[A-Z][A-Z0-9]{2,}(?:-[A-Z0-9]+)*\b")


def _derive_product_and_amount(
    state: AdvisorState, planned: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Product id and amount, taken from whatever call the planner did emit, then
    from ``proposed_amount`` and the client's own words. The model reliably names
    the product in one call even when it omits the requirements call."""
    product_id: str | None = None
    amount: str | None = None
    for call in planned:
        args = call.get("args", {})
        product_id = product_id or args.get("target_product_id") or args.get("product_id")
        if amount is None and args.get("amount") is not None:
            amount = str(args["amount"])
    if amount is None and (proposed := state.get("proposed_amount")) is not None:
        amount = str(proposed.amount)
    if product_id is None:
        match = _PRODUCT_CODE.search(state.get("client_input_text", ""))
        product_id = match.group(0) if match else None
    return product_id, amount


def _ensure_transactional_tools(
    state: AdvisorState, planned: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The transaction FormSpec is built from ``get_transaction_requirements`` and,
    for a buy or switch, ``check_suitability`` (ADR-0005). ``mode=ANY`` function
    calling returns a single call, so a real model routinely emits one of the two
    and drops the other. The graph adds the missing calls structurally rather than
    trusting the model to plan the full set."""
    intent = state.get("intent")
    if intent is Intent.ADVISORY_RECOMMEND:
        # A regulated recommendation needs products to evaluate. mode=ANY returns
        # a single call, so the model may skip the search: add it structurally,
        # filtered to the client's risk band and horizon so the candidates can pass.
        if not any(c["name"] == "search_investment_products" for c in planned):
            return [
                *planned,
                {"name": "search_investment_products", "args": _search_filters(state)},
            ]
        return planned
    if intent not in TRANSACTIONAL_INTENTS:
        return planned
    product_id, amount = _derive_product_and_amount(state, planned)
    if not product_id:
        return planned
    out = list(planned)
    if not any(c["name"] == "get_transaction_requirements" for c in out):
        args: dict[str, Any] = {
            "product_id": product_id,
            "operation": _TRANSACT_OPERATION.get(Intent(str(intent)), "BUY"),
        }
        if amount is not None:
            args["amount"] = amount
        out.append({"name": "get_transaction_requirements", "args": args})
    if (
        intent in (Intent.TRANSACT_BUY, Intent.TRANSACT_SWITCH)
        and amount is not None
        and not any(c["name"] == "check_suitability" for c in out)
    ):
        out.append(
            {"name": "check_suitability", "args": {"product_id": product_id, "amount": amount}}
        )
    return out


async def tool_execution(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    """Execute the planned calls in parallel under a total time budget."""
    planned = state.get("planned_calls", [])
    if not planned:
        return {"needs_more_tools": False, "planned_calls": []}

    limits = deps.settings.limits
    started = time.perf_counter()
    results: dict[str, ToolResult] = dict(state.get("tool_results", {}))
    provenance: dict[str, ProvenanceEntry] = dict(state.get("provenance", {}))
    client_id = state["client_id"]

    async def run(call: dict[str, Any]) -> ToolResult:
        return await deps.gateway.call(
            call["name"], client_id=client_id, args=dict(call.get("args", {}))
        )

    with node_span("tool_execution", turn_id=state.get("turn_id"), calls=len(planned)):
        outcomes = await asyncio.gather(
            *(asyncio.wait_for(run(c), timeout=limits.total_tool_budget_s) for c in planned),
            return_exceptions=True,
        )

    for call, outcome in zip(planned, outcomes, strict=True):
        name = call["name"]
        if isinstance(outcome, BaseException):
            error = "TIMEOUT" if isinstance(outcome, TimeoutError) else type(outcome).__name__
            results[name] = ToolResult(name=name, ok=False, error=error)
            continue
        result = outcome
        spec = deps.registry.get(name)
        if result.ok and spec.untrusted_content:
            result = await _scan_untrusted(result, deps)
        results[name] = result
        if result.ok:
            record_provenance(result, provenance)

    rounds = state.get("tool_rounds", 0) + 1
    calls_made = state.get("tool_calls_made", 0) + len(planned)
    elapsed = time.perf_counter() - started
    failed_retryable = [
        n
        for n, r in results.items()
        if not r.ok
        and r.error in {"TIMEOUT", "CIRCUIT_OPEN"}
        and not deps.registry.get(n).fail_open
    ]
    needs_more = bool(
        failed_retryable
        and rounds < limits.max_tool_rounds
        and rounds < 2
        and calls_made < limits.max_tool_calls_per_turn
        and elapsed < limits.total_tool_budget_s
    )
    log.info(
        "tools.round_complete",
        turn_id=state.get("turn_id"),
        round=rounds,
        calls=len(planned),
        elapsed_ms=round(elapsed * 1000),
        needs_more=needs_more,
        failed=[n for n, r in results.items() if not r.ok],
    )
    return {
        "tool_results": results,
        "provenance": provenance,
        "tool_rounds": rounds,
        "tool_calls_made": calls_made,
        "needs_more_tools": needs_more,
        # A retry round re-plans only the failed calls.
        "planned_calls": [c for c in planned if c["name"] in failed_retryable]
        if needs_more
        else [],
    }


async def _scan_untrusted(result: ToolResult, deps: Dependencies) -> ToolResult:
    """Retrieved third-party text is the one place hostile content can reach the
    prompt: scan every item and drop hits (docs/04-backend/03 §3)."""
    data = result.data
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return result
    kept: list[Any] = []
    dropped = 0
    for item in data["items"]:
        text = " ".join(str(item.get(k, "")) for k in ("title", "summary", "content", "text"))
        try:
            hostile = await deps.guardrail.scan_retrieved(text=text)
        except Exception:
            hostile = True
        if hostile:
            dropped += 1
            continue
        kept.append(item)
    if dropped:
        log.warning(
            "tools.untrusted_content_dropped",
            tool=result.name,
            dropped=dropped,
            security_event=True,
        )
        get_metrics().guardrail_blocks.add(1, {"stage": "retrieved", "reason": "INJECTION"})
    return result.model_copy(update={"data": {**data, "items": kept}})


async def agent_core(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    """Generate the response. Model choice is by intent, decided upstream."""
    if state.get("error") is not None:
        return {}
    intent = state["intent"]
    vertex = deps.settings.vertex
    if intent in DEEP_MODEL_INTENTS:
        model = vertex.model_deep
    else:
        model = await deps.flags.get("advisor.model.primary") or vertex.model_fast
    max_tokens = (
        vertex.max_output_tokens_voice
        if state.get("channel") == "voice"
        else vertex.max_output_tokens_chat
    )
    rewrite_hint = None
    if (verdict := state.get("guardrail_output")) is not None and verdict.violations:
        rewrite_hint = (
            "Tu respuesta anterior fue rechazada por: "
            + ", ".join(verdict.violations)
            + ". Reescríbela corrigiendo exactamente eso, sin cifras exactas ni garantías."
        )
    degradation_notice = DEGRADATION_NOTICE_ES if state.get("degraded_from") else None
    system_prompt = deps.prompts.render_system(
        state,
        tool_declarations=deps.registry.declarations_for(str(intent)),
        degradation_notice=degradation_notice,
    )
    task = deps.prompts.task_prompt(intent)
    if task:
        system_prompt = f"{system_prompt}\n\n{task}"

    started = time.perf_counter()
    with node_span("agent_core", turn_id=state.get("turn_id"), model=model, intent=str(intent)):
        try:
            generation = await asyncio.wait_for(
                deps.generator.generate(
                    state=state,
                    system_prompt=system_prompt,
                    model=model,
                    max_tokens=max_tokens,
                    rewrite_hint=rewrite_hint,
                ),
                timeout=deps.settings.limits.model_timeout_s,
            )
        except Exception as exc:
            log.error("agent_core.generation_failed", reason=type(exc).__name__, model=model)
            return {
                "speech": None,
                "error": AgentError(
                    code="MODEL_UNAVAILABLE", message_es=MODEL_DOWN_ES, escalate=True
                ),
                "model_meta": {**state.get("model_meta", {}), "model": model, "failed": True},
            }
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    metrics = get_metrics()
    metrics.model_tokens.add(
        generation.input_tokens, {"direction": "input", "model": model, "intent": str(intent)}
    )
    metrics.model_tokens.add(
        generation.output_tokens, {"direction": "output", "model": model, "intent": str(intent)}
    )
    metrics.model_ttft_ms.record(generation.ttft_ms or elapsed_ms, {"model": model})

    update: dict[str, Any] = {
        "speech": generation.speech,
        "model_meta": {
            **state.get("model_meta", {}),
            "provider": generation.provider,
            "model": model,
            "prompt_version": deps.prompts.version,
            "temperature": vertex.temperature,
            "top_p": vertex.top_p,
            "seed": vertex.seed,
            "max_output_tokens": max_tokens,
            "input_tokens": generation.input_tokens,
            "output_tokens": generation.output_tokens,
            "ttft_ms": generation.ttft_ms or elapsed_ms,
            "safety_verdicts": {"blocked": generation.safety_blocked},
            "rewrite_attempt": state.get("rewrite_attempts", 0),
        },
    }
    if generation.safety_blocked:
        update["error"] = AgentError(code="BLOCKED_OUTPUT", message_es=MODEL_DOWN_ES, escalate=True)

    if intent in ADVISORY_INTENTS or intent in TRANSACTIONAL_INTENTS:
        candidate_ids = generation.candidate_product_ids or _candidate_ids_from_tools(state)
        update["candidate_products"] = await _resolve_candidates(candidate_ids, state, deps)
        amount = generation.proposed_amount
        if amount is None and (existing := state.get("proposed_amount")) is not None:
            amount = existing.decimal
        if amount is None:
            # The model did not emit the <monto> block: take the figure the client
            # stated ("200 mil"), so the suitability engine evaluates a real amount
            # instead of zero (which fails every minimum-investment rule).
            amount = extract_amount(state.get("client_input_text", ""))
        if amount is not None:
            currency = "MXN"
            if update["candidate_products"]:
                currency = update["candidate_products"][0].currency
            update["proposed_amount"] = Money.of(Decimal(amount), currency)
    return update


def _search_filters(state: AdvisorState) -> dict[str, Any]:
    """Profile-scoped product search for a forced advisory recommendation: the
    client's risk ceiling and horizon, so the returned products can survive the
    suitability engine (an unfiltered search returns products the profile rejects)."""
    filters: dict[str, Any] = {"limit": 8}
    profile = state.get("investor_profile")
    if profile is not None:
        ceiling = {
            "bajo": ["bajo"],
            "medio": ["bajo", "medio"],
            "alto": ["bajo", "medio", "alto"],
        }
        filters["risk_level"] = ceiling.get(str(profile.max_risk), ["bajo", "medio"])
        filters["horizon_months_max"] = profile.horizon_months
    return filters


def _candidate_ids_from_tools(state: AdvisorState) -> list[str]:
    """Product ids present in this turn's tool results, in order, deduplicated.

    Fallback for when the model did not emit the ``<candidatos>`` block: the
    suitability engine still decides razonabilidad, so proposing the search hits
    is safe. Capped at four (the committee-profile ceiling)."""
    ids: list[str] = []
    for name in ("search_investment_products", "get_product_detail", "get_product_risk_profile"):
        result = state.get("tool_results", {}).get(name)
        if result is None or not result.ok or not isinstance(result.data, dict):
            continue
        items = result.data.get("items")
        if isinstance(items, list):
            ids.extend(
                str(i["product_id"]) for i in items if isinstance(i, dict) and i.get("product_id")
            )
        elif result.data.get("product_id"):
            ids.append(str(result.data["product_id"]))
    return list(dict.fromkeys(ids))[:4]


async def _resolve_candidates(
    ids: list[str], state: AdvisorState, deps: Dependencies
) -> list[ProductProfile]:
    """Candidate ids from the model become committee profiles from the product
    master. A product without a committee profile is not recommendable
    (docs/07-data-governance/01 §4) and is dropped here."""
    existing = {p.product_id: p for p in state.get("candidate_products", [])}
    resolved: list[ProductProfile] = []
    for product_id in dict.fromkeys(ids):
        if product_id in existing:
            resolved.append(existing[product_id])
            continue
        result = await deps.gateway.call(
            "get_product_risk_profile", client_id=None, args={"product_id": product_id}
        )
        if not result.ok or not isinstance(result.data, dict):
            log.warning("agent_core.candidate_without_profile", product_id=product_id)
            continue
        payload = {k: v for k, v in result.data.items() if k != "as_of"}
        try:
            resolved.append(ProductProfile.model_validate(payload))
        except ValueError:
            log.warning("agent_core.candidate_profile_invalid", product_id=product_id)
    return resolved
