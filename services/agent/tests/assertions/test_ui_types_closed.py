"""docs/03-mobile/01 §4: ``ui_payload`` is a typed component list with a closed
type registry. An unknown type renders nothing on the client, so the server
must never invent one; adding a type is a client release.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from actinver_agent.graph.state import UI_COMPONENT_TYPES, UIComponent

#: The registry documented for the client renderer (docs/03-mobile/01 §4) plus
#: the additive server-side types the composer emits (docs/04-backend/04 §4:
#: "New ui component type - Yes - unknown types render nothing").
DOCUMENTED = {
    "portfolio_summary",
    "portfolio_positions",
    "attribution_bars",
    "product_list",
    "product_detail",
    "product_comparison",
    "quote_table",
    "news_list",
    "simulation_chart",
    "suitability_summary",
    "warning_banner",
    "form_spec",
    "citations",
    "escalation_offer",
}
ADDITIVE = {
    "cash_summary",
    "research_list",
    "calendar_list",
    "fee_breakdown",
    "transaction_list",
    "statement_link",
    "accounts_list",
    "services_guide",
    "escalation_card",
    "complaint_card",
    "order_receipt",
    "disclosure",
    "profile_update_offer",
}


def test_documented_types_are_all_present() -> None:
    missing = DOCUMENTED - UI_COMPONENT_TYPES
    assert not missing, f"documented ui types missing from the registry: {missing}"


def test_registry_is_exactly_documented_plus_additive() -> None:
    assert UI_COMPONENT_TYPES == DOCUMENTED | ADDITIVE


def test_unknown_type_is_rejected_server_side() -> None:
    with pytest.raises(ValidationError):
        UIComponent(type="html_blob", payload={})  # type: ignore[arg-type]


def test_component_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        UIComponent(type="citations", payload={"items": []}, html="<b>x</b>")  # type: ignore[call-arg]
