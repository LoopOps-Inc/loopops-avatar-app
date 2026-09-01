"""Response composition - the only node permitted to write the final ``speech``.

Implements split-channel rendering (ADR-0006): narrative to the voice channel,
exact figures to the in-app data channel. Enforces the provenance invariant on
``ui_payload`` (every numeric scalar traces to a tool result) and offers
escalation on every refusal (control DP-07).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from langchain_core.messages import AIMessage

from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import (
    AdvisorState,
    Citation,
    SuitabilityOutcome,
    UIComponent,
    UIComponentType,
    normalise_figure,
)
from actinver_agent.observability.setup import get_metrics, node_span
from actinver_agent.tools.registry import derived_keys

log = structlog.get_logger(__name__)

#: Tool → closed UI component type (docs/03-mobile/01 §4).
_RENDER: dict[str, UIComponentType] = {
    "get_portfolio_positions": "portfolio_positions",
    "get_portfolio_performance": "portfolio_summary",
    "get_portfolio_attribution": "attribution_bars",
    "get_cash_balance": "cash_summary",
    "get_client_accounts": "accounts_list",
    "search_investment_products": "product_list",
    "get_product_detail": "product_detail",
    "compare_products": "product_comparison",
    "get_market_quote": "quote_table",
    "search_market_news": "news_list",
    "get_actinver_research": "research_list",
    "get_economic_calendar": "calendar_list",
    "simulate_investment": "simulation_chart",
    "calculate_fees_and_taxes": "fee_breakdown",
    "get_transaction_history": "transaction_list",
    "get_account_statements": "statement_link",
    "get_investment_services_guide": "services_guide",
    "escalate_to_advisor": "escalation_card",
    "file_complaint": "complaint_card",
}

#: Components whose payloads are not tool-derived figures and are exempt from
#: the provenance check (they carry ids, texts, versions, form limits).
_PROVENANCE_EXEMPT: frozenset[str] = frozenset(
    {
        "form_spec",
        "disclosure",
        "escalation_offer",
        "escalation_card",
        "complaint_card",
        "suitability_summary",
        "warning_banner",
        "citations",
        "order_receipt",
        "profile_update_offer",
        "services_guide",
        "statement_link",
        "accounts_list",
    }
)

ESCALATION_CTA_ES = "Hablar con mi asesor"


async def response_composer(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:  # noqa: ARG001
    with node_span("response_composer", turn_id=state.get("turn_id")):
        if (error := state.get("error")) is not None:
            get_metrics().escalations.add(1, {"reason": error.code})
            ui: list[UIComponent] = [_escalation_offer(error.code)]
            if error.code == "PROFILE_EXPIRED":
                ui.insert(
                    0,
                    UIComponent(
                        type="profile_update_offer",
                        payload={"cta_es": "Actualizar mi perfil", "reason": "PROFILE_EXPIRED"},
                        source="system",
                    ),
                )
            if (form := state.get("form_spec")) is not None and error.code in {"AUDIT_UNAVAILABLE"}:
                log.info("composer.form_withheld", form_id=form.form_id)
            return {
                "speech": error.message_es,
                "ui_payload": ui,
                "citations": [],
                "messages": [AIMessage(content=error.message_es)],
            }

        speech = state.get("speech") or ""
        provenance_keys = set(state.get("provenance", {}).keys())
        ui = []
        citations: list[Citation] = []

        for name, result in state.get("tool_results", {}).items():
            if not result.ok or result.data is None:
                continue
            component = _render(name, result.data, result.as_of)
            if component is None:
                continue
            if component.type not in _PROVENANCE_EXEMPT and not _provenance_ok(
                component.payload, provenance_keys
            ):
                # The composer refuses to emit a figure it cannot trace.
                log.error("composer.unsourced_figure", component=component.type, tool=name)
                get_metrics().guardrail_blocks.add(
                    1, {"stage": "composer", "reason": "UNSOURCED_UI"}
                )
                continue
            ui.append(component)
            citations.extend(_citations(name, result.data))

        if (report := state.get("suitability")) is not None:
            ui.append(
                UIComponent(
                    type="suitability_summary",
                    payload={
                        "verdict_id": report.verdict_id,
                        "ruleset_version": report.ruleset_version,
                        "evaluations": [
                            {
                                "product_id": e.product_id,
                                "outcome": str(e.outcome),
                                "rule_id": e.rule_id,
                                "rationale": e.rationale,
                                "warnings": e.warnings,
                            }
                            for e in report.evaluations
                            if e.outcome is not SuitabilityOutcome.NO_APTO
                        ],
                    },
                    as_of=report.evaluated_at,
                    source="service:suitability",
                )
            )
            for evaluation in report.evaluations:
                if evaluation.outcome is SuitabilityOutcome.APTO_CON_ADVERTENCIA:
                    ui.append(
                        UIComponent(
                            type="warning_banner",
                            payload={
                                "product_id": evaluation.product_id,
                                "warnings": evaluation.warnings,
                            },
                            as_of=report.evaluated_at,
                            source="service:suitability",
                        )
                    )

        for disclosure_id, text in state.get("disclosure_texts", {}).items():
            ui.append(
                UIComponent(
                    type="disclosure",
                    payload={
                        "id": disclosure_id,
                        "text": text,
                        "version": state.get("disclosures_shown", {}).get(disclosure_id),
                    },
                    source="legal:disclosures",
                )
            )

        if (form := state.get("form_spec")) is not None and not state.get("receipt"):
            ui.append(
                UIComponent(
                    type="form_spec",
                    payload=form.model_dump(mode="json"),
                    as_of=form.issued_at,
                    source="service:transaction_planner",
                )
            )

        if state.get("receipt"):
            # execute_transaction already rendered the receipt card.
            ui.extend(c for c in state.get("ui_payload", []) if c.type == "order_receipt")

        if citations:
            ui.append(
                UIComponent(
                    type="citations",
                    payload={"items": [c.model_dump(mode="json") for c in citations]},
                    source="tool:citations",
                )
            )

        if state.get("degraded_from") is not None:
            ui.append(_escalation_offer("DEGRADED_ADVISORY"))

    return {
        "speech": speech,
        "ui_payload": ui,
        "citations": citations,
        "messages": [AIMessage(content=speech)] if speech else [],
    }


def _escalation_offer(reason: str) -> UIComponent:
    return UIComponent(
        type="escalation_offer",
        payload={"reason": reason, "cta_es": ESCALATION_CTA_ES},
        source="system",
    )


def _render(tool_name: str, data: Any, as_of: Any) -> UIComponent | None:
    component_type = _RENDER.get(tool_name)
    if component_type is None:
        return None
    payload = data if isinstance(data, dict) else {"items": data}
    return UIComponent(
        type=component_type, payload=payload, as_of=as_of, source=f"tool:{tool_name}"
    )


def _citations(tool_name: str, data: Any) -> list[Citation]:
    if tool_name not in {"search_market_news", "get_actinver_research"}:
        return []
    items = data.get("items", []) if isinstance(data, dict) else data
    out: list[Citation] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        out.append(
            Citation(
                title=str(item.get("title", "")),
                url=item.get("url"),
                source=str(item.get("source", tool_name)),
                published_at=item.get("published_at"),
                ref=item.get("ref"),
            )
        )
    return out


def _provenance_ok(payload: dict[str, Any], provenance_keys: set[str]) -> bool:
    """Every numeric scalar in a component must trace to a tool result."""
    if not provenance_keys:
        return not _has_numbers(payload)

    def check(node: Any) -> bool:
        if isinstance(node, dict):
            is_money = set(node) == {"amount", "currency"}
            for key, value in node.items():
                if is_money and key == "amount":
                    try:
                        if not _known(float(Decimal(str(value))), provenance_keys):
                            return False
                    except (InvalidOperation, ValueError):
                        return False
                elif not check(value):
                    return False
            return True
        if isinstance(node, list):
            return all(check(v) for v in node)
        if isinstance(node, bool) or node is None or isinstance(node, str):
            return True
        if isinstance(node, (int, float)):
            return _known(float(node), provenance_keys)
        return True

    return check(payload)


def _known(value: float, keys: set[str]) -> bool:
    return normalise_figure(value) in keys or any(k in keys for k in derived_keys(value))


def _has_numbers(node: Any) -> bool:
    if isinstance(node, dict):
        return any(_has_numbers(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_numbers(v) for v in node)
    return isinstance(node, (int, float)) and not isinstance(node, bool)
