"""The SQL-backed core: dataset rows mapped onto the CoreBankingPort shapes.

The mapping is pure and tested without a database; the queries themselves live
in ``InvestmentOfficeSqlCore`` and are exercised against the seeded schema.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from actinver_agent.clients.investment_office_core import (
    _asset_class,
    _map_cash,
    _map_client_context,
    _map_positions,
)


def test_asset_class_maps_what_the_dataset_actually_states() -> None:
    assert _asset_class("ACCION", "RV") == "renta_variable_local"
    assert _asset_class("ETF", "RV") == "renta_variable_global"
    assert _asset_class("FONDO", "RV") == "renta_variable_local"
    assert _asset_class("BONO", "RF") == "deuda_corporativa"
    assert _asset_class("ETF", "RF") == "deuda_corporativa"
    assert _asset_class("FONDO", "RF") == "deuda_corporativa"


def test_unknown_instruments_fall_back_to_the_default_limit_bucket() -> None:
    """An unrecognised pair must not silently borrow a permissive limit; the
    rules engine applies ``__default__`` to any class it does not know."""
    assert _asset_class("SWAP", "XX") == "no_clasificado"
    assert _asset_class(None, None) == "no_clasificado"


ROWS = [
    {
        "clave_emisora": "ACTIAI",
        "desc_emisora": "Actinver Renta Variable",
        "desc_instrumento": "FONDO",
        "desc_tipo_producto": "RV",
        "cantidad_titulos": "75000.0000",
        "posicion_total": "7500000.0000",
        "fecha_valuacion": "2024-03-31",
    },
    {
        "clave_emisora": "VGSH",
        "desc_emisora": "Vanguard Short-Term Treasury",
        "desc_instrumento": "ETF",
        "desc_tipo_producto": "RF",
        "cantidad_titulos": "1000.0000",
        "posicion_total": "2500000.0000",
        "fecha_valuacion": "2024-03-31",
    },
]


def test_positions_carry_real_weights_and_total() -> None:
    result = _map_positions(ROWS, cash=Decimal("0"))

    assert result["total_market_value"] == {"amount": "10000000.00", "currency": "MXN"}
    weights = {p["product_id"]: p["weight_pct"] for p in result["positions"]}
    assert weights == {"ACTIAI": 75.0, "VGSH": 25.0}
    assert result["as_of"] == "2024-03-31"


def test_positions_omit_cost_basis_because_the_dataset_forbids_projecting_precio() -> None:
    """Trap T5 of the InvestmentOffice schema: ``precio`` must never be
    projected, so no cost basis can be derived. Reporting the market value as
    the cost would invent a zero return."""
    for position in _map_positions(ROWS, cash=Decimal("0"))["positions"]:
        assert position["cost_basis"] is None


def test_cash_and_liquidity_come_from_the_balances_not_from_a_constant() -> None:
    """`liquid_pct` feeds suitability rule R-018. Hardcoding it would fabricate
    an input to a regulated control, so it is derived from real cash."""
    result = _map_positions(ROWS, cash=Decimal("2500000"))

    assert result["cash"] == {"amount": "2500000.00", "currency": "MXN"}
    # 2.5M cash over 10M positions + 2.5M cash.
    assert result["liquid_pct"] == 0.2


def test_positions_of_an_empty_portfolio_do_not_divide_by_zero() -> None:
    result = _map_positions([], cash=Decimal("0"))

    assert result["positions"] == []
    assert result["total_market_value"] == {"amount": "0.00", "currency": "MXN"}
    assert result["liquid_pct"] == 0.0


def test_cash_reports_the_newest_cut_across_products() -> None:
    """Balances carry one `fecha_corte` per product and they differ; `as_of`
    must be a real date from the rows, never fabricated."""
    balances = [
        {
            "producto": "PPR",
            "naturaleza": "SALDO",
            "monto_mxn": "10.00",
            "fecha_corte": "2023-12-31",
        },
        {
            "producto": "MANDATOS",
            "naturaleza": "SALDO",
            "monto_mxn": "10.00",
            "fecha_corte": "2026-05-07",
        },
    ]

    assert _map_cash(balances)["as_of"] == "2026-05-07"


def test_cash_without_any_balance_row_refuses_rather_than_invent_a_date() -> None:
    from actinver_agent.clients.investment_office_core import DatasetIncomplete

    with pytest.raises(DatasetIncomplete):
        _map_cash([])


def test_cash_comes_from_the_dataset_balances_not_from_a_percentage() -> None:
    balances = [
        {
            "producto": "FONDOS",
            "naturaleza": "SALDO",
            "monto_mxn": "120000.00",
            "fecha_corte": "2024-03-31",
        },
        {
            "producto": "PPR",
            "naturaleza": "SALDO",
            "monto_mxn": "80000.00",
            "fecha_corte": "2024-03-31",
        },
    ]

    result = _map_cash(balances)

    assert result["available"] == {"amount": "200000.00", "currency": "MXN"}
    assert result["pending"] == {"amount": "0.00", "currency": "MXN"}
    assert result["settlements"] == []


def test_cash_ignores_flow_figures_that_are_not_balances() -> None:
    """Trap T4: rows are tagged with ``naturaleza``; only SALDO is a balance."""
    balances = [
        {
            "producto": "FONDOS",
            "naturaleza": "SALDO",
            "monto_mxn": "100.00",
            "fecha_corte": "2024-03-31",
        },
        {
            "producto": "CEDE",
            "naturaleza": "FLUJO_NETO",
            "monto_mxn": "999.00",
            "fecha_corte": "2024-03-31",
        },
        {
            "producto": "PRLV",
            "naturaleza": "CAPITAL_INICIAL",
            "monto_mxn": "555.00",
            "fecha_corte": "2024-03-31",
        },
    ]

    assert _map_cash(balances)["available"] == {"amount": "100.00", "currency": "MXN"}


@pytest.mark.parametrize("period", ["MTD", "YTD", "1Y"])
def test_performance_is_refused_for_periods_the_snapshots_cannot_support(period: str) -> None:
    """Two annual snapshots cannot produce a month-to-date return. Answering
    with a differently-scoped figure would misstate it to the client, so the
    tool fails and the composer simply renders nothing."""
    from actinver_agent.clients.investment_office_core import PeriodNotAvailable, _check_period

    with pytest.raises(PeriodNotAvailable):
        _check_period(period, snapshots=["2023-03-31", "2024-03-31"])


# ── client context: the real client and their real advisor ───────────────────

BASE_CONTEXT = {
    "as_of": "2026-09-02",
    "first_name": "Plantilla",
    "register": "tu",
    "risk_category": "moderado",
    "entitlements": {"advisory": True, "execution": True},
    "promotor": {
        "name": "Laura Méndez",
        "phone": "+52 55 1103 6600",
        "hours": "lunes a viernes 8:30-18:00",
    },
}

CLIENTE = {"nombre": "Mariano", "apellido_paterno": "Salas", "nombre_perfil": "Agresivo"}
ASESORES = [{"nombre_completo": "Alberto Hernán Guevara", "correo_electronico": "a@b.com"}]


def test_client_context_uses_the_real_name_and_advisor() -> None:
    context = _map_client_context(BASE_CONTEXT, CLIENTE, ASESORES)

    assert context["first_name"] == "Mariano"
    assert context["promotor"]["name"] == "Alberto Hernán Guevara"
    assert context["risk_category"] == "agresivo"


def test_client_context_keeps_the_institutional_contact_channel() -> None:
    """The dataset carries the advisor's email but no phone or hours, so those
    stay on the firm's default rather than being invented."""
    context = _map_client_context(BASE_CONTEXT, CLIENTE, ASESORES)

    assert context["promotor"]["phone"] == BASE_CONTEXT["promotor"]["phone"]
    assert context["promotor"]["hours"] == BASE_CONTEXT["promotor"]["hours"]


def test_client_context_keeps_entitlements_which_the_dataset_does_not_carry() -> None:
    """Entitlements gate advisory and execution. The schema says nothing about
    them, so they are never fabricated from this source."""
    context = _map_client_context(BASE_CONTEXT, CLIENTE, ASESORES)

    assert context["entitlements"] == BASE_CONTEXT["entitlements"]


def test_client_context_without_an_advisor_keeps_the_default_contact() -> None:
    context = _map_client_context(BASE_CONTEXT, CLIENTE, [])

    assert context["promotor"] == BASE_CONTEXT["promotor"]
