"""Stale valuations are surfaced, not narrated as if they were current.

``UIComponent`` carries ``as_of`` "so the client can render staleness"
(graph/state.py). The InvestmentOffice dataset makes this concrete: a client's
positions are valued at 2023-03-31 while their balances carry a 2026 cut-off,
and the answer read as if both were today's.
"""

from __future__ import annotations

from datetime import UTC, datetime

from actinver_agent.graph.nodes.composer import _stale_valuation_warning
from actinver_agent.graph.state import UIComponent

TODAY = datetime(2026, 9, 2, tzinfo=UTC)


def _component(type_: str, as_of: datetime | None) -> UIComponent:
    return UIComponent(type=type_, payload={}, as_of=as_of, source="tool:x")  # type: ignore[arg-type]


def test_a_fresh_valuation_raises_no_warning() -> None:
    ui = [_component("portfolio_positions", datetime(2026, 8, 31, tzinfo=UTC))]

    assert _stale_valuation_warning(ui, today=TODAY, max_age_days=45) is None


def test_a_stale_valuation_is_named_with_its_date() -> None:
    ui = [_component("portfolio_positions", datetime(2023, 3, 31, tzinfo=UTC))]

    warning = _stale_valuation_warning(ui, today=TODAY, max_age_days=45)

    assert warning is not None
    assert warning.type == "warning_banner"
    assert warning.payload["severity"] == "warning"
    assert "2023-03-31" in warning.payload["message"]


def test_the_oldest_valuation_decides_when_dates_are_mixed() -> None:
    """Trap T2: balances and positions can carry different cut-offs. The client
    must be told about the oldest figure on screen, not the newest."""
    ui = [
        _component("cash_summary", datetime(2026, 5, 7, tzinfo=UTC)),
        _component("portfolio_positions", datetime(2023, 3, 31, tzinfo=UTC)),
    ]

    warning = _stale_valuation_warning(ui, today=TODAY, max_age_days=45)

    assert warning is not None
    assert "2023-03-31" in warning.payload["message"]
    assert "2026-05-07" not in warning.payload["message"]


def test_components_without_a_valuation_date_are_ignored() -> None:
    ui = [_component("escalation_offer", None), _component("citations", None)]

    assert _stale_valuation_warning(ui, today=TODAY, max_age_days=45) is None


def test_no_components_raises_no_warning() -> None:
    assert _stale_valuation_warning([], today=TODAY, max_age_days=45) is None


def test_a_naive_valuation_date_is_compared_without_blowing_up() -> None:
    """Tool results carry naive datetimes; comparing them against an aware
    ``now`` raised TypeError and failed the whole turn in the composer."""
    ui = [_component("portfolio_positions", datetime(2023, 3, 31))]

    warning = _stale_valuation_warning(ui, today=TODAY, max_age_days=45)

    assert warning is not None
    assert "2023-03-31" in warning.payload["message"]


def test_naive_and_aware_dates_mix_without_error() -> None:
    ui = [
        _component("cash_summary", datetime(2026, 5, 7, tzinfo=UTC)),
        _component("portfolio_positions", datetime(2023, 3, 31)),
    ]

    assert _stale_valuation_warning(ui, today=TODAY, max_age_days=45) is not None
