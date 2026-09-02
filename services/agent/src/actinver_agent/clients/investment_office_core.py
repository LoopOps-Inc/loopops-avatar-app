"""``CoreBankingPort`` over the InvestmentOffice dataset (``CORE_PROVIDER=sql``).

Client-scoped figures - positions, balances, contracts, movements, profile -
come from the seeded ``investmentofficedb`` schema, so two investors no longer
share a portfolio. Everything that is *not* client data (the product catalogue,
committee diversification limits, the simulation and fee engines) has no table
in that schema and is delegated to ``fallback`` unchanged.

The schema's documented traps are honoured here, not worked around:

* **T5 - never project ``precio``.** No cost basis can be derived, so
  ``Position.cost_basis`` is left unset rather than filled with the market
  value, which would assert a zero return the data does not support.
* **T4 - figures carry ``naturaleza``.** Only ``SALDO`` rows are balances;
  ``FLUJO_NETO`` and ``CAPITAL_INICIAL`` are not cash.
* **T2 - mixed valuation dates.** ``as_of`` reports the newest snapshot the
  positions actually carry.

The dataset holds two annual snapshots, so month- or year-to-date returns are
not derivable. Rather than answer with a differently scoped figure, the
performance and attribution calls fail and the composer renders nothing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, NoReturn

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from actinver_agent.clients.investment_office_sql import InvestmentOfficeSqlCore

log = structlog.get_logger(__name__)

MXN = "MXN"

#: What the dataset states about an instrument, mapped onto the asset classes
#: the committee's diversification limits are keyed by. The pair
#: (``desc_instrumento``, ``desc_tipo_producto``) is all the schema asserts;
#: per-ticker classification would be invented, so an unrecognised pair becomes
#: ``no_clasificado`` and the rules engine applies its ``__default__`` limit.
_ASSET_CLASS: dict[tuple[str, str], str] = {
    ("ACCION", "RV"): "renta_variable_local",
    ("FONDO", "RV"): "renta_variable_local",
    ("ETF", "RV"): "renta_variable_global",
    ("BONO", "RF"): "deuda_corporativa",
    ("ETF", "RF"): "deuda_corporativa",
    ("FONDO", "RF"): "deuda_corporativa",
}

#: Balance rows only (trap T4).
_BALANCE = "SALDO"


class PeriodNotAvailable(RuntimeError):
    """The requested period cannot be derived from the dataset's snapshots."""


class DatasetIncomplete(RuntimeError):
    """The dataset carries no row to answer with, and none may be invented."""


def _money(amount: Decimal | str | int) -> dict[str, str]:
    return {"amount": str(Decimal(str(amount)).quantize(Decimal("0.01"))), "currency": MXN}


def _asset_class(instrumento: str | None, tipo_producto: str | None) -> str:
    if not instrumento or not tipo_producto:
        return "no_clasificado"
    return _ASSET_CLASS.get((instrumento.upper(), tipo_producto.upper()), "no_clasificado")


def _map_positions(rows: list[dict[str, Any]], *, cash: Decimal) -> dict[str, Any]:
    invested = sum(
        (Decimal(str(r["posicion_total"])) for r in rows if r.get("posicion_total")), Decimal("0")
    )
    snapshots = sorted({str(r["fecha_valuacion"]) for r in rows if r.get("fecha_valuacion")})
    positions = [
        {
            "product_id": r["clave_emisora"],
            "name": r.get("desc_emisora") or r["clave_emisora"],
            "asset_class": _asset_class(r.get("desc_instrumento"), r.get("desc_tipo_producto")),
            "quantity": float(r["cantidad_titulos"]) if r.get("cantidad_titulos") else 0.0,
            "market_value": _money(r["posicion_total"]),
            # Trap T5: `precio` is off limits, so there is no cost basis.
            "cost_basis": None,
            "weight_pct": (
                round(float(Decimal(str(r["posicion_total"])) / invested * 100), 4)
                if invested
                else 0.0
            ),
            "currency": MXN,
        }
        for r in rows
        if r.get("posicion_total")
    ]
    total = invested + cash
    return {
        # T2: the newest snapshot the positions actually carry.
        "as_of": snapshots[-1] if snapshots else None,
        "total_market_value": _money(invested),
        "cash": _money(cash),
        # Feeds suitability rule R-018, so it is derived, never assumed. The
        # schema states no liquidity horizon for an instrument, so only cash
        # counts as liquid: that understates liquidity and can only warn more,
        # which is the safe direction for a suitability control.
        "liquid_pct": round(float(cash / total), 4) if total else 0.0,
        "positions": positions,
    }


def _map_cash(balances: list[dict[str, Any]]) -> dict[str, Any]:
    saldos = [b for b in balances if b.get("naturaleza") == _BALANCE]
    cortes = sorted({str(b["fecha_corte"]) for b in saldos if b.get("fecha_corte")})
    if not cortes:
        raise DatasetIncomplete("the client carries no balance row with a cut-off date")
    return {
        "as_of": cortes[-1],
        "available": _money(_available(saldos)),
        # The schema records no unsettled cash, so it is zero, not invented.
        "pending": _money(0),
        "settlements": [],
    }


def _available(saldos: list[dict[str, Any]]) -> Decimal:
    return sum(
        (Decimal(str(b["monto_mxn"])) for b in saldos if b.get("monto_mxn") is not None),
        Decimal("0"),
    )


def _map_client_context(
    base: dict[str, Any], cliente: dict[str, Any], asesores: list[dict[str, Any]]
) -> dict[str, Any]:
    """Overlay what the dataset states onto the fallback's context.

    The schema carries the client's name, their risk profile and the advisor who
    owns their contracts. It carries no entitlements (which gate advisory and
    execution) and no phone or hours for the advisor, only an email. Those keep
    the fallback's values instead of being invented, so the person named is
    real while the contact channel stays the firm's.
    """
    context = {**base, "promotor": dict(base.get("promotor") or {})}
    if nombre := cliente.get("nombre"):
        context["first_name"] = str(nombre).split()[0]
    if perfil := cliente.get("nombre_perfil"):
        context["risk_category"] = str(perfil).lower()
    if asesores and (name := asesores[0].get("nombre_completo")):
        context["promotor"]["name"] = str(name)
    return context


def _check_period(period: str, *, snapshots: list[str]) -> NoReturn:
    """Refuse a period the dataset's snapshots cannot produce.

    The dataset carries annual cuts only. A month- or year-to-date return
    cannot be computed from them, and answering with the annual figure under a
    monthly label would misstate it to the client.
    """
    if len(snapshots) < 2:
        raise PeriodNotAvailable(f"{period}: the dataset carries a single valuation date")
    raise PeriodNotAvailable(
        f"{period}: the dataset carries annual snapshots ({snapshots[0]} to {snapshots[-1]}), "
        "which cannot produce this period"
    )


class InvestmentOfficeCore:
    """Client data from the dataset; everything else from ``fallback``."""

    def __init__(self, engine: AsyncEngine, fallback: Any) -> None:
        self._engine = engine
        self._sql = InvestmentOfficeSqlCore(engine)
        self._fallback = fallback

    # ── client-scoped: the dataset is the source of truth ────────────────────

    async def _id_cliente(self, conn: Any, client_id: str) -> int:
        return await self._sql.resolve_id_cliente(conn, client_id)

    async def get_client_context(self, *, client_id: str) -> dict[str, Any]:
        base = await self._fallback.get_client_context(client_id=client_id)
        async with self._engine.connect() as conn:
            id_cliente = await self._id_cliente(conn, client_id)
            cliente = await self._sql.obtener_cliente(conn, id_cliente=id_cliente)
            asesores = await self._sql.obtener_asesor(conn, id_cliente=id_cliente)
        return _map_client_context(base, cliente, asesores)

    async def get_positions(self, *, client_id: str) -> dict[str, Any]:
        async with self._engine.connect() as conn:
            id_cliente = await self._id_cliente(conn, client_id)
            rows = await self._sql.obtener_posiciones(conn, id_cliente=id_cliente, limite=100)
            balances = await self._sql.obtener_saldos_por_producto(conn, id_cliente=id_cliente)
        cash = _available([b for b in balances if b.get("naturaleza") == _BALANCE])
        return _map_positions(rows, cash=cash)

    async def get_cash_balance(self, *, client_id: str) -> dict[str, Any]:
        async with self._engine.connect() as conn:
            id_cliente = await self._id_cliente(conn, client_id)
            balances = await self._sql.obtener_saldos_por_producto(conn, id_cliente=id_cliente)
        return _map_cash(balances)

    async def get_accounts(self, *, client_id: str) -> dict[str, Any]:
        async with self._engine.connect() as conn:
            id_cliente = await self._id_cliente(conn, client_id)
            contratos = await self._sql.listar_contratos(conn, id_cliente=id_cliente)
        return {
            "as_of": None,
            "accounts": [
                {
                    "account_id": str(c["num_contrato"]),
                    "label": f"{c.get('subtipo_contrato') or c['tipo_contrato']} ····"
                    f"{str(c['num_contrato'])[-4:]}",
                    "type": str(c["tipo_contrato"]).lower(),
                    "currency": MXN,
                    "eligible_for": ["debit", "credit"],
                }
                for c in contratos
            ],
        }

    async def get_performance(self, *, client_id: str, period: str = "MTD") -> dict[str, Any]:
        async with self._engine.connect() as conn:
            id_cliente = await self._id_cliente(conn, client_id)
            total = await self._sql.obtener_posicion_total(conn, id_cliente=id_cliente)
        _check_period(period, snapshots=list(total.get("fechas_valuacion") or []))

    async def get_attribution(
        self,
        *,
        client_id: str,
        period: str = "MTD",
        granularity: str = "asset_class",  # noqa: ARG002 - refused before it is read
    ) -> dict[str, Any]:
        return await self.get_performance(client_id=client_id, period=period)

    async def get_transaction_history(
        self,
        *,
        client_id: str,
        **kw: Any,  # noqa: ARG002 - the dataset query takes no filters yet
    ) -> dict[str, Any]:
        async with self._engine.connect() as conn:
            id_cliente = await self._id_cliente(conn, client_id)
            movimientos = await self._sql.obtener_movimientos(conn, id_cliente=id_cliente)
        return {"as_of": None, "items": movimientos.get("items", [])}

    # ── not client data: no table in this schema ─────────────────────────────

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fallback, name)


class InvestmentOfficeCrm:
    """Escalations named after the client's real advisor.

    ``CrmPort`` is a separate port, so the core adapter cannot reach it: the
    escalation card would keep naming the synthetic template's promotor while
    the session contact named the real one. Only ``promotor_name`` comes from
    the dataset; the case id, SLA and everything else stay on ``fallback``.
    """

    def __init__(self, engine: AsyncEngine, fallback: Any) -> None:
        self._engine = engine
        self._sql = InvestmentOfficeSqlCore(engine)
        self._fallback = fallback

    async def create_escalation(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        result: dict[str, Any] = await self._fallback.create_escalation(client_id=client_id, **kw)
        async with self._engine.connect() as conn:
            id_cliente = await self._sql.resolve_id_cliente(conn, client_id)
            asesores = await self._sql.obtener_asesor(conn, id_cliente=id_cliente)
        if asesores and (name := asesores[0].get("nombre_completo")):
            result = {**result, "promotor_name": str(name)}
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fallback, name)
