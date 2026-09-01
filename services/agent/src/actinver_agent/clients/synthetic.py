"""Deterministic synthetic core systems for local, dev and CI.

The architecture is built against a contract-first mock of the Actinver core
(docs/00-overview/03 §4: "Build against a contract-first mock; the tool
interfaces are already written that way"). Staging uses generated data with
realistic distributions and never real client records (docs/08-operations/01).
This module is that generator, reduced to a small fixed cohort so demos and
golden tests are reproducible.

Demo clients (``client_id`` is the token subject):

| client_id             | first_name | perfil       | horizonte | conocimiento | asesorado | ejecución | perfil vigente |
|-----------------------|------------|--------------|-----------|--------------|-----------|-----------|----------------|
| ``cl_demo_moderado``  | José       | moderado     | 24 m      | intermedio   | sí        | sí        | hasta 2027-02-11 |
| ``cl_demo_conservador`` | Ana      | conservador  | 12 m      | basico       | **no**    | sí        | hasta 2027-05-01 |
| ``cl_demo_agresivo``  | Luis       | agresivo     | 60 m      | avanzado     | sí        | sí        | hasta 2027-08-15 |
| ``cl_demo_vencido``   | Marta      | moderado     | 24 m      | intermedio   | sí        | sí        | **vencido** 2026-01-01 |

``cl_demo_moderado`` reproduces the worked example in
docs/01-architecture/01 §4.2: market value 4,187,203.55 MXN, MTD +0.87 %,
attribution deuda gubernamental +118 bp, deuda corporativa +21 bp, renta
variable local -52 bp.

Faults can be forced with ``set_fault("core_down", True)`` etc. so the
fail-closed branches are exercisable from tests and from the local stack.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from actinver_agent.graph.state import Money

MX_TZ = timezone(timedelta(hours=-6))

FAULTS: set[str] = set()
KNOWN_FAULTS: frozenset[str] = frozenset(
    {"core_down", "profile_missing", "market_down", "news_down", "crm_down", "oms_down"}
)


class SyntheticFailures:
    """Fault toggles for local outage drills."""

    @staticmethod
    def set_fault(name: str, on: bool) -> None:
        set_fault(name, on)

    @staticmethod
    def clear() -> None:
        FAULTS.clear()


def set_fault(name: str, on: bool) -> None:
    if name not in KNOWN_FAULTS:
        raise ValueError(f"unknown fault {name!r}; known: {sorted(KNOWN_FAULTS)}")
    if on:
        FAULTS.add(name)
    else:
        FAULTS.discard(name)


class CoreUnavailable(RuntimeError):
    pass


def now_mx() -> datetime:
    return datetime.now(MX_TZ).replace(microsecond=0)


def as_of() -> str:
    return now_mx().isoformat()


def _money(amount: Decimal | int | str, currency: str = "MXN") -> dict[str, str]:
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Money.of(value, currency).model_dump()


# ── Product catalogue and committee profiles (DCGSI Anexo 4) ──────────────────

PRODUCTS: dict[str, dict[str, Any]] = {
    "ACTIGOB-BF": {
        "name": "Actinver Gubernamental",
        "committee_version": 31,
        "risk_level": "bajo",
        "complexity": "simple",
        "liquidity_hours": 24,
        "min_holding_months": 1,
        "minimum_investment": "10000",
        "currency": "MXN",
        "annual_cost_pct": 0.85,
        "asset_class": "deuda_gubernamental",
        "approved_at": "2026-06-01",
        "annual_volatility_pct": 1.8,
        "expected_return_pct": 9.1,
        "objective": "Preservar el capital invirtiendo en deuda gubernamental mexicana de corto plazo.",
        "returns": {"MTD": 0.71, "YTD": 6.2, "1Y": 9.4, "3Y": 8.7},
    },
    "ACTICETES-BF": {
        "name": "Actinver CETES",
        "committee_version": 18,
        "risk_level": "bajo",
        "complexity": "simple",
        "liquidity_hours": 24,
        "min_holding_months": 0,
        "minimum_investment": "1000",
        "currency": "MXN",
        "annual_cost_pct": 0.60,
        "asset_class": "deuda_gubernamental",
        "approved_at": "2026-05-15",
        "annual_volatility_pct": 0.9,
        "expected_return_pct": 8.6,
        "objective": "Replicar el rendimiento de los CETES a 28 días con liquidez diaria.",
        "returns": {"MTD": 0.68, "YTD": 5.9, "1Y": 8.9, "3Y": 8.1},
    },
    "ACTICORP-BF": {
        "name": "Actinver Deuda Corporativa",
        "committee_version": 27,
        "risk_level": "medio",
        "complexity": "simple",
        "liquidity_hours": 48,
        "min_holding_months": 6,
        "minimum_investment": "25000",
        "currency": "MXN",
        "annual_cost_pct": 1.10,
        "asset_class": "deuda_corporativa",
        "approved_at": "2026-04-20",
        "annual_volatility_pct": 4.2,
        "expected_return_pct": 10.3,
        "objective": "Obtener un rendimiento superior a la deuda gubernamental con emisores corporativos mexicanos.",
        "returns": {"MTD": 0.52, "YTD": 6.8, "1Y": 10.1, "3Y": 9.2},
    },
    "ACTIMIX-BF": {
        "name": "Actinver Balanceado",
        "committee_version": 22,
        "risk_level": "medio",
        "complexity": "moderada",
        "liquidity_hours": 48,
        "min_holding_months": 12,
        "minimum_investment": "50000",
        "currency": "MXN",
        "annual_cost_pct": 1.45,
        "asset_class": "mixto",
        "approved_at": "2026-03-10",
        "annual_volatility_pct": 8.5,
        "expected_return_pct": 11.0,
        "objective": "Combinar deuda y renta variable con una distribución de activos moderada.",
        "returns": {"MTD": 0.31, "YTD": 7.4, "1Y": 11.6, "3Y": 9.8},
    },
    "ACTIVAR-RV": {
        "name": "Actinver Renta Variable México",
        "committee_version": 22,
        "risk_level": "alto",
        "complexity": "moderada",
        "liquidity_hours": 72,
        "min_holding_months": 24,
        "minimum_investment": "50000",
        "currency": "MXN",
        "annual_cost_pct": 1.80,
        "asset_class": "renta_variable_local",
        "approved_at": "2026-02-02",
        "annual_volatility_pct": 18.0,
        "expected_return_pct": 12.5,
        "objective": "Crecimiento de capital a largo plazo con acciones listadas en la BMV y BIVA.",
        "returns": {"MTD": -2.6, "YTD": 4.1, "1Y": 13.9, "3Y": 10.4},
    },
    "ACTIGLOB-RV": {
        "name": "Actinver Renta Variable Global",
        "committee_version": 19,
        "risk_level": "alto",
        "complexity": "compleja",
        "liquidity_hours": 72,
        "min_holding_months": 36,
        "minimum_investment": "100000",
        "currency": "USD",
        "annual_cost_pct": 1.95,
        "asset_class": "renta_variable_global",
        "approved_at": "2026-01-25",
        "annual_volatility_pct": 16.5,
        "expected_return_pct": 11.8,
        "objective": "Exposición a mercados accionarios globales a través del SIC.",
        "returns": {"MTD": 1.2, "YTD": 9.3, "1Y": 15.2, "3Y": 12.1},
    },
    "ACTIUSD-BF": {
        "name": "Actinver Deuda Dólares",
        "committee_version": 15,
        "risk_level": "bajo",
        "complexity": "simple",
        "liquidity_hours": 48,
        "min_holding_months": 3,
        "minimum_investment": "5000",
        "currency": "USD",
        "annual_cost_pct": 0.95,
        "asset_class": "cobertura_cambiaria",
        "approved_at": "2026-05-05",
        "annual_volatility_pct": 2.5,
        "expected_return_pct": 4.5,
        "objective": "Cobertura cambiaria con instrumentos de deuda denominados en dólares.",
        "returns": {"MTD": 0.35, "YTD": 3.1, "1Y": 4.6, "3Y": 4.2},
    },
    "ACTIREAL-BF": {
        "name": "Actinver Activos Reales",
        "committee_version": 9,
        "risk_level": "alto",
        "complexity": "compleja",
        "liquidity_hours": None,
        "min_holding_months": 60,
        "minimum_investment": "250000",
        "currency": "MXN",
        "annual_cost_pct": 2.20,
        "asset_class": "alternativos",
        "approved_at": "2025-11-30",
        "annual_volatility_pct": 12.0,
        "expected_return_pct": 13.0,
        "objective": "Inversión en infraestructura y bienes raíces a través de vehículos listados; sin liquidez diaria.",
        "returns": {"MTD": 0.9, "YTD": 8.8, "1Y": 14.0, "3Y": 11.3},
    },
}

DIVERSIFICATION_LIMITS: dict[str, float] = {
    "__default__": 0.25,
    "deuda_gubernamental": 0.60,
    "deuda_corporativa": 0.35,
    "mixto": 0.30,
    "renta_variable_local": 0.25,
    "renta_variable_global": 0.20,
    "cobertura_cambiaria": 0.20,
    "alternativos": 0.10,
}

# ── Demo cohort (DCGSI Anexo 3 profiles) ──────────────────────────────────────

CLIENTS: dict[str, dict[str, Any]] = {
    "cl_demo_moderado": {
        "first_name": "José",
        "register": "tu",
        "entitlements": {
            "contracted_for_advised_services": True,
            "contracted_for_execution": True,
            "permitted_product_families": ["deuda", "mixto", "renta_variable"],
            "daily_avatar_minutes_remaining": 60,
        },
        "profile": {
            "profile_id": "pf_moderado_01",
            "version": 7,
            "risk_category": "moderado",
            "horizon_months": 24,
            "knowledge_level": "intermedio",
            "capacity_band": "B",
            "objectives": ["crecimiento_moderado", "liquidez"],
            "permitted_currencies": ["MXN"],
            "min_liquidity_pct": 0.10,
            "is_sophisticated": False,
            "assessed_at": "2026-02-11",
            "expires_at": "2027-02-11",
        },
        "portfolio_total": "4187203.55",
        "holdings": [
            ("ACTIGOB-BF", 0.46),
            ("ACTICORP-BF", 0.22),
            ("ACTIVAR-RV", 0.18),
            ("ACTIMIX-BF", 0.09),
        ],
        "cash_pct": 0.05,
        "performance": {
            "MTD": (0.87, "36127.44"),
            "QTD": (1.9, "78044.10"),
            "YTD": (6.4, "251880.97"),
            "1Y": (9.8, "373716.20"),
            "3Y": (8.9, "0"),
            "SINCE_INCEPTION": (31.2, "0"),
        },
        "attribution": [
            ("Deuda gubernamental", 118),
            ("Deuda corporativa", 21),
            ("Renta variable local", -52),
        ],
        "promotor": {
            "name": "Laura Méndez",
            "phone": "+52 55 1103 6600",
            "hours": "lunes a viernes 8:30-18:00",
        },
    },
    "cl_demo_conservador": {
        "first_name": "Ana",
        "register": "tu",
        "entitlements": {
            "contracted_for_advised_services": False,
            "contracted_for_execution": True,
            "permitted_product_families": ["deuda"],
            "daily_avatar_minutes_remaining": 60,
        },
        "profile": {
            "profile_id": "pf_conservador_01",
            "version": 3,
            "risk_category": "conservador",
            "horizon_months": 12,
            "knowledge_level": "basico",
            "capacity_band": "A",
            "objectives": ["preservacion_de_capital"],
            "permitted_currencies": ["MXN"],
            "min_liquidity_pct": 0.20,
            "is_sophisticated": False,
            "assessed_at": "2026-05-01",
            "expires_at": "2027-05-01",
        },
        "portfolio_total": "812450.00",
        "holdings": [("ACTICETES-BF", 0.55), ("ACTIGOB-BF", 0.35)],
        "cash_pct": 0.10,
        "performance": {
            "MTD": (0.62, "5000.38"),
            "QTD": (1.7, "13600.00"),
            "YTD": (5.8, "44560.00"),
            "1Y": (8.7, "65000.00"),
            "3Y": (8.0, "0"),
            "SINCE_INCEPTION": (17.4, "0"),
        },
        "attribution": [("Deuda gubernamental", 62)],
        "promotor": {
            "name": "Carlos Rivera",
            "phone": "+52 55 1103 6601",
            "hours": "lunes a viernes 9:00-18:00",
        },
    },
    "cl_demo_agresivo": {
        "first_name": "Luis",
        "register": "tu",
        "entitlements": {
            "contracted_for_advised_services": True,
            "contracted_for_execution": True,
            "permitted_product_families": ["deuda", "mixto", "renta_variable", "alternativos"],
            "daily_avatar_minutes_remaining": 60,
        },
        "profile": {
            "profile_id": "pf_agresivo_01",
            "version": 5,
            "risk_category": "agresivo",
            "horizon_months": 60,
            "knowledge_level": "avanzado",
            "capacity_band": "D",
            "objectives": ["crecimiento_agresivo"],
            "permitted_currencies": ["MXN", "USD"],
            "min_liquidity_pct": 0.05,
            "is_sophisticated": True,
            "assessed_at": "2026-08-15",
            "expires_at": "2027-08-15",
        },
        "portfolio_total": "12650000.00",
        "holdings": [
            ("ACTIVAR-RV", 0.35),
            ("ACTIGLOB-RV", 0.30),
            ("ACTIMIX-BF", 0.15),
            ("ACTIGOB-BF", 0.15),
        ],
        "cash_pct": 0.05,
        "performance": {
            "MTD": (-0.9, "-113850.00"),
            "QTD": (2.8, "354200.00"),
            "YTD": (7.9, "999350.00"),
            "1Y": (14.2, "1796300.00"),
            "3Y": (11.1, "0"),
            "SINCE_INCEPTION": (48.0, "0"),
        },
        "attribution": [
            ("Renta variable local", -91),
            ("Renta variable global", 36),
            ("Deuda gubernamental", 14),
            ("Mixto", -49),
        ],
        "promotor": {
            "name": "Sofía Herrera",
            "phone": "+52 55 1103 6602",
            "hours": "lunes a viernes 8:00-19:00",
        },
    },
    "cl_demo_vencido": {
        "first_name": "Marta",
        "register": "tu",
        "entitlements": {
            "contracted_for_advised_services": True,
            "contracted_for_execution": True,
            "permitted_product_families": ["deuda", "mixto"],
            "daily_avatar_minutes_remaining": 60,
        },
        "profile": {
            "profile_id": "pf_vencido_01",
            "version": 2,
            "risk_category": "moderado",
            "horizon_months": 24,
            "knowledge_level": "intermedio",
            "capacity_band": "B",
            "objectives": ["crecimiento_moderado"],
            "permitted_currencies": ["MXN"],
            "min_liquidity_pct": 0.10,
            "is_sophisticated": False,
            "assessed_at": "2025-01-01",
            "expires_at": "2026-01-01",
        },
        "portfolio_total": "1500000.00",
        "holdings": [("ACTIGOB-BF", 0.60), ("ACTIMIX-BF", 0.30)],
        "cash_pct": 0.10,
        "performance": {
            "MTD": (0.55, "8250.00"),
            "QTD": (1.6, "24000.00"),
            "YTD": (6.0, "90000.00"),
            "1Y": (9.0, "135000.00"),
            "3Y": (8.5, "0"),
            "SINCE_INCEPTION": (22.0, "0"),
        },
        "attribution": [("Deuda gubernamental", 45), ("Mixto", 10)],
        "promotor": {
            "name": "Laura Méndez",
            "phone": "+52 55 1103 6600",
            "hours": "lunes a viernes 8:30-18:00",
        },
    },
}


def _client(client_id: str) -> dict[str, Any]:
    if "core_down" in FAULTS:
        raise CoreUnavailable("core banking unavailable (fault injected)")
    try:
        return CLIENTS[client_id]
    except KeyError as exc:
        raise KeyError(f"unknown client {client_id}") from exc


def _stable_int(*parts: str, mod: int) -> int:
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:4], "big") % mod


def _positions(client: dict[str, Any]) -> tuple[list[dict[str, Any]], Decimal]:
    total = Decimal(client["portfolio_total"])
    positions: list[dict[str, Any]] = []
    allocated = Decimal("0")
    holdings = client["holdings"]
    for index, (product_id, weight) in enumerate(holdings):
        product = PRODUCTS[product_id]
        value = (total * Decimal(str(weight))).quantize(Decimal("0.01"))
        if index == len(holdings) - 1:
            # Absorb rounding so the sum reconciles exactly with the total.
            cash = (total * Decimal(str(client["cash_pct"]))).quantize(Decimal("0.01"))
            value = total - allocated - cash
        allocated += value
        cost = (value / Decimal("1.06")).quantize(Decimal("0.01"))
        nav = Decimal("2.4531") + Decimal(index) / 10
        positions.append(
            {
                "product_id": product_id,
                "name": product["name"],
                "asset_class": product["asset_class"],
                "quantity": float((value / nav).quantize(Decimal("0.0001"))),
                "market_value": _money(
                    value, product["currency"] if product["currency"] == "MXN" else "MXN"
                ),
                "cost_basis": _money(cost),
                "weight_pct": round(float(value / total) * 100, 2),
                "currency": "MXN",
            }
        )
    return positions, total


class SyntheticCoreBanking:
    """Implements ``CoreBankingPort`` with the fixed cohort above."""

    async def get_client_context(self, *, client_id: str) -> dict[str, Any]:
        client = _client(client_id)
        return {
            "as_of": as_of(),
            "first_name": client["first_name"],
            "register": client["register"],
            "risk_category": client["profile"]["risk_category"],
            "entitlements": dict(client["entitlements"]),
            "promotor": dict(client["promotor"]),
        }

    async def get_investor_profile(self, *, client_id: str) -> dict[str, Any]:
        client = _client(client_id)
        if "profile_missing" in FAULTS:
            raise CoreUnavailable("profiling system unavailable (fault injected)")
        return {"as_of": as_of(), **client["profile"]}

    async def get_positions(self, *, client_id: str) -> dict[str, Any]:
        client = _client(client_id)
        positions, total = _positions(client)
        liquid = sum(
            Decimal(p["market_value"]["amount"])
            for p in positions
            if (PRODUCTS[p["product_id"]]["liquidity_hours"] or 999) <= 72
        )
        cash = (total * Decimal(str(client["cash_pct"]))).quantize(Decimal("0.01"))
        return {
            "as_of": as_of(),
            "total_market_value": _money(total),
            "cash": _money(cash),
            "liquid_pct": round(float((liquid + cash) / total), 4),
            "positions": positions,
        }

    async def get_performance(self, *, client_id: str, period: str = "MTD") -> dict[str, Any]:
        client = _client(client_id)
        pct, amount = client["performance"].get(period, client["performance"]["MTD"])
        valuation = (now_mx().date().replace(day=1) - timedelta(days=1)).isoformat()
        return {
            "as_of": as_of(),
            "period": period,
            "period_return_pct": pct,
            "period_return_amount": _money(amount),
            "market_value": _money(client["portfolio_total"]),
            "valuation_date": valuation,
        }

    async def get_attribution(
        self, *, client_id: str, period: str = "MTD", granularity: str = "asset_class"
    ) -> dict[str, Any]:
        client = _client(client_id)
        contributions = [{"sleeve": sleeve, "bps": bps} for sleeve, bps in client["attribution"]]
        if granularity == "product":
            contributions = [
                {"sleeve": PRODUCTS[pid]["name"], "bps": round(bps * w * 2)}
                for (pid, w), (_, bps) in zip(
                    client["holdings"], client["attribution"], strict=False
                )
            ]
        elif granularity == "currency":
            total = sum(b for _, b in client["attribution"])
            contributions = [{"sleeve": "MXN", "bps": total}]
        return {
            "as_of": as_of(),
            "period": period,
            "granularity": granularity,
            "total_bps": sum(c["bps"] for c in contributions),
            "contributions": contributions,
        }

    async def get_cash_balance(self, *, client_id: str) -> dict[str, Any]:
        client = _client(client_id)
        total = Decimal(client["portfolio_total"])
        cash = (total * Decimal(str(client["cash_pct"]))).quantize(Decimal("0.01"))
        pending = (cash * Decimal("0.12")).quantize(Decimal("0.01"))
        settle = (now_mx().date() + timedelta(days=1)).isoformat()
        return {
            "as_of": as_of(),
            "available": _money(cash - pending),
            "pending": _money(pending),
            "settlements": [{"date": settle, "amount": _money(pending)}],
        }

    async def get_accounts(self, *, client_id: str) -> dict[str, Any]:
        _client(client_id)
        suffix = f"{_stable_int(client_id, 'acc', mod=10000):04d}"
        return {
            "as_of": as_of(),
            "accounts": [
                {
                    "account_id": f"acc_{client_id[-8:]}_inv",
                    "label": f"Contrato de inversión ····{suffix}",
                    "type": "inversion",
                    "currency": "MXN",
                    "eligible_for": ["debit", "credit"],
                },
                {
                    "account_id": f"acc_{client_id[-8:]}_chq",
                    "label": f"Cuenta de cheques ····{int(suffix) % 9973:04d}",
                    "type": "cheques",
                    "currency": "MXN",
                    "eligible_for": ["debit"],
                },
            ],
        }

    async def get_transaction_history(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        client = _client(client_id)
        limit = int(kw.get("limit") or 20)
        op_filter = kw.get("operation_type") or "ALL"
        items: list[dict[str, Any]] = []
        today = now_mx().date()
        kinds = ["BUY", "DIVIDEND", "FEE", "SELL"]
        for i in range(12):
            kind = kinds[i % len(kinds)]
            if op_filter != "ALL" and kind != op_filter:
                continue
            product_id = client["holdings"][i % len(client["holdings"])][0]
            amount = Decimal(1000 + _stable_int(client_id, str(i), mod=90000))
            items.append(
                {
                    "operation_id": f"op_{_stable_int(client_id, 'op', str(i), mod=10**8):08d}",
                    "date": (today - timedelta(days=7 * (i + 1))).isoformat(),
                    "type": kind,
                    "product_id": product_id,
                    "amount": _money(amount if kind != "FEE" else amount / 100),
                    "status": "LIQUIDADA",
                }
            )
        return {"as_of": as_of(), "items": items[:limit]}

    async def get_statement(self, *, client_id: str, year: int, month: int) -> dict[str, Any]:
        _client(client_id)
        token = hashlib.sha256(f"{client_id}:{year}:{month}".encode()).hexdigest()[:24]
        expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        return {
            "as_of": as_of(),
            "year": year,
            "month": month,
            "url": f"https://documentos.actinver.local/estados/{year}/{month:02d}/{token}.pdf",
            "expires_at": expires,
        }

    async def search_products(self, **filters: Any) -> dict[str, Any]:
        if "core_down" in FAULTS:
            raise CoreUnavailable("product master unavailable (fault injected)")
        items = []
        risk_levels = filters.get("risk_level")
        asset_classes = filters.get("asset_class")
        currency = filters.get("currency")
        horizon = filters.get("horizon_months_max")
        liquidity = filters.get("liquidity_hours_max")
        min_inv = filters.get("min_investment_max")
        limit = int(filters.get("limit") or 8)
        for product_id, p in PRODUCTS.items():
            if risk_levels and p["risk_level"] not in risk_levels:
                continue
            if asset_classes and p["asset_class"] not in asset_classes:
                continue
            if currency and p["currency"] != currency:
                continue
            if horizon is not None and p["min_holding_months"] > int(horizon):
                continue
            if liquidity is not None and (
                p["liquidity_hours"] is None or p["liquidity_hours"] > int(liquidity)
            ):
                continue
            if min_inv is not None and Decimal(p["minimum_investment"]) > Decimal(str(min_inv)):
                continue
            items.append(_product_summary(product_id, p))
        return {"as_of": as_of(), "items": items[:limit]}

    async def get_product_detail(self, *, product_id: str) -> dict[str, Any]:
        p = _product(product_id)
        return {
            "as_of": as_of(),
            **_product_summary(product_id, p),
            "objective": p["objective"],
            "policy": "Política de inversión conforme al prospecto vigente autorizado por la CNBV.",
            "fees": {
                "annual_cost_pct": p["annual_cost_pct"],
                "entry_fee_pct": 0.0,
                "exit_fee_pct": 0.0 if p["min_holding_months"] == 0 else 0.5,
            },
            "historical_returns": [
                {"period": period, "return_pct": value, "as_of": as_of()}
                for period, value in p["returns"].items()
            ],
            "dici_url": f"https://documentos.actinver.local/dici/{product_id}-v{p['committee_version']}.pdf",
            "prospectus_url": f"https://documentos.actinver.local/prospectos/{product_id}.pdf",
        }

    async def get_product_profile(self, *, product_id: str) -> dict[str, Any]:
        p = _product(product_id)
        return {
            "as_of": as_of(),
            "product_id": product_id,
            "name": p["name"],
            "committee_version": p["committee_version"],
            "risk_level": p["risk_level"],
            "complexity": p["complexity"],
            "liquidity_hours": p["liquidity_hours"],
            "min_holding_months": p["min_holding_months"],
            "minimum_investment": p["minimum_investment"],
            "currency": p["currency"],
            "annual_cost_pct": p["annual_cost_pct"],
            "asset_class": p["asset_class"],
            "approved_at": p["approved_at"],
        }

    async def compare_products(self, *, product_ids: list[str]) -> dict[str, Any]:
        items = [_product_summary(pid, _product(pid)) for pid in product_ids]
        for item in items:
            item["historical_returns"] = [
                {"period": k, "return_pct": v, "as_of": as_of()}
                for k, v in PRODUCTS[item["product_id"]]["returns"].items()
            ]
        return {"as_of": as_of(), "items": items}

    async def get_diversification_limits(self) -> dict[str, float]:
        if "core_down" in FAULTS:
            raise CoreUnavailable("committee system unavailable (fault injected)")
        return dict(DIVERSIFICATION_LIMITS)

    async def get_transaction_requirements(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        _client(client_id)
        product_id = kw["product_id"]
        p = _product(product_id)
        operation = kw.get("operation", "BUY")
        target = kw.get("target_product_id")
        minimum = Decimal(p["minimum_investment"])
        maximum = Decimal("2500000")
        fields: list[dict[str, Any]] = [
            {
                "key": "amount",
                "type": "money",
                "currency": p["currency"],
                "label": "Monto a invertir"
                if operation in ("BUY", "RECURRING", "SWITCH")
                else "Monto a retirar",
                "required": True,
                "min": str(minimum),
                "max": str(maximum),
                "help": "Disponible en tu cuenta: se valida al confirmar",
            },
            {
                "key": "account_id",
                "type": "select",
                "label": "Cuenta de cargo" if operation == "BUY" else "Cuenta de abono",
                "options_source": "tool:get_client_accounts",
                "required": True,
            },
        ]
        if operation in ("BUY", "RECURRING"):
            fields.append(
                {
                    "key": "recurring",
                    "type": "boolean",
                    "label": "Hacerlo mensual",
                    "required": False,
                    "default": False,
                }
            )
        disclosures = [
            {"id": "PAST_PERF", "ack": False},
            {"id": "RISK_ACK", "ack": True},
            {"id": "COSTS", "ack": False},
            {"id": "SETTLEMENT", "ack": False},
        ]
        if operation in ("SELL", "REDEEM"):
            disclosures.append({"id": "TAX_WITHHOLDING", "ack": False})
        requirements: dict[str, Any] = {
            "as_of": as_of(),
            "operation": operation,
            "product": {
                "id": product_id,
                "name": p["name"],
                "risk_level": p["risk_level"],
                "currency": p["currency"],
            },
            "fields": fields,
            "disclosures": disclosures,
            "execution": {
                "cutoff_local": "13:30",
                "timezone": "America/Mexico_City",
                "settlement": "T+1" if (p["liquidity_hours"] or 24) <= 24 else "T+2",
                "valuation": "precio de cierre del día",
            },
            "limits": {
                "min": _money(minimum, p["currency"]),
                "max": _money(maximum, p["currency"]),
            },
        }
        if target:
            tp = _product(target)
            requirements["target_product"] = {
                "id": target,
                "name": tp["name"],
                "risk_level": tp["risk_level"],
                "currency": tp["currency"],
            }
        return requirements

    async def simulate_investment(self, **kw: Any) -> dict[str, Any]:
        product_id = kw["product_id"]
        p = _product(product_id)
        amount = Decimal(str(kw["amount"]))
        months = int(kw["horizon_months"])
        monthly = Decimal(str(kw.get("monthly_contribution") or 0))
        years = Decimal(months) / 12
        expected = Decimal(str(p["expected_return_pct"])) / 100
        vol = Decimal(str(p["annual_volatility_pct"])) / 100

        def grow(rate: Decimal) -> Decimal:
            growth = (1 + rate) ** years
            contributions = monthly * 12 * years * (1 + rate / 2)
            return (amount * growth + contributions).quantize(Decimal("0.01"))

        return {
            "as_of": as_of(),
            "product_id": product_id,
            "amount": _money(amount, p["currency"]),
            "horizon_months": months,
            "annual_volatility_pct": p["annual_volatility_pct"],
            "scenarios": {
                "pessimistic": _money(grow(expected - vol), p["currency"]),
                "base": _money(grow(expected), p["currency"]),
                "optimistic": _money(grow(expected + vol), p["currency"]),
            },
            "disclosures": ["SIMULATION_NOT_PROMISE", "PAST_PERF"],
        }

    async def calculate_fees_and_taxes(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        _client(client_id)
        p = _product(kw["product_id"])
        amount = Decimal(str(kw["amount"]))
        holding = int(kw.get("holding_months") or 12)
        annual = (
            amount * Decimal(str(p["annual_cost_pct"])) / 100 * Decimal(holding) / 12
        ).quantize(Decimal("0.01"))
        gain_estimate = (
            amount * Decimal(str(p["expected_return_pct"])) / 100 * Decimal(holding) / 12
        )
        isr = (gain_estimate * Decimal("0.20")).quantize(Decimal("0.01"))
        return {
            "as_of": as_of(),
            "fees": [
                {"name": "Comisión de administración", "amount": _money(annual, p["currency"])}
            ],
            "estimated_isr_withholding": _money(isr, p["currency"]),
            "total": _money(annual + isr, p["currency"]),
            "disclosures": ["COSTS", "TAX_WITHHOLDING"],
        }

    async def get_device_public_key(self, *, client_id: str, device_id: str) -> str | None:  # noqa: ARG002
        return None

    async def health(self) -> bool:
        return "core_down" not in FAULTS


def _product(product_id: str) -> dict[str, Any]:
    if "core_down" in FAULTS:
        raise CoreUnavailable("product master unavailable (fault injected)")
    try:
        return PRODUCTS[product_id]
    except KeyError as exc:
        raise KeyError(f"unknown product {product_id}") from exc


def _product_summary(product_id: str, p: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "name": p["name"],
        "risk_level": p["risk_level"],
        "complexity": p["complexity"],
        "asset_class": p["asset_class"],
        "currency": p["currency"],
        "liquidity_hours": p["liquidity_hours"],
        "min_holding_months": p["min_holding_months"],
        "minimum_investment": _money(p["minimum_investment"], p["currency"]),
        "annual_cost_pct": p["annual_cost_pct"],
        "committee_version": p["committee_version"],
    }


# ── Market data ────────────────────────────────────────────────────────────────

_QUOTES: dict[str, tuple[float, str, float]] = {
    "USDMXN": (18.42, "MXN", -0.35),
    "IPC": (58120.55, "MXN", 0.42),
    "CETES28": (8.05, "PCT", 0.0),
    "TIIE28": (8.28, "PCT", 0.0),
    "UDI": (8.5312, "MXN", 0.01),
    "SPX": (6210.12, "USD", 0.15),
    "AMXB": (17.85, "MXN", 1.1),
    "WALMEX": (62.30, "MXN", -0.6),
}


class SyntheticMarketData:
    async def get_quotes(self, *, symbols: list[str]) -> dict[str, Any]:
        if "market_down" in FAULTS:
            raise RuntimeError("market data vendor unavailable (fault injected)")
        quotes = []
        for symbol in symbols:
            key = symbol.upper().replace("/", "")
            price, currency, change = _QUOTES.get(
                key, (100.0 + _stable_int(key, mod=500) / 10, "MXN", 0.0)
            )
            quotes.append(
                {
                    "symbol": symbol.upper(),
                    "price": price,
                    "currency": currency,
                    "change_pct": change,
                    "timestamp": as_of(),
                    "delayed": True,
                    "delay_minutes": 20,
                }
            )
        return {"as_of": as_of(), "quotes": quotes}

    async def get_calendar(self, **kw: Any) -> dict[str, Any]:
        if "market_down" in FAULTS:
            raise RuntimeError("market data vendor unavailable (fault injected)")
        regions = kw.get("regions") or ["MX"]
        today = now_mx().date()
        events = [
            {
                "date": (today + timedelta(days=10)).isoformat(),
                "region": "MX",
                "name": "Decisión de política monetaria de Banxico",
                "importance": "alta",
            },
            {
                "date": (today + timedelta(days=8)).isoformat(),
                "region": "MX",
                "name": "INPC quincenal (INEGI)",
                "importance": "media",
            },
            {
                "date": (today + timedelta(days=16)).isoformat(),
                "region": "US",
                "name": "Decisión de tasas de la Reserva Federal (FOMC)",
                "importance": "alta",
            },
            {
                "date": (today + timedelta(days=4)).isoformat(),
                "region": "US",
                "name": "Reporte de empleo (nóminas no agrícolas)",
                "importance": "alta",
            },
        ]
        return {
            "as_of": as_of(),
            "events": [e for e in events if e["region"] in regions or "GLOBAL" in regions],
        }

    async def health(self) -> bool:
        return "market_down" not in FAULTS


# ── News and research (allow-listed hosts only) ───────────────────────────────

_NEWS: list[dict[str, Any]] = [
    {
        "title": "Banxico recorta la tasa de referencia 25 pb",
        "url": "https://www.elfinanciero.com.mx/economia/2026/08/14/banxico-recorta-tasa-25-pb/",
        "source": "elfinanciero.com.mx",
        "published_at": "2026-08-14T13:05:00-06:00",
        "summary": "La Junta de Gobierno redujo la tasa objetivo en 25 puntos base, en línea con lo esperado, y favoreció a los instrumentos de deuda gubernamental de corto plazo.",
        "topics": ["banxico", "tasa", "deuda", "peso", "gubernamental"],
    },
    {
        "title": "El peso se aprecia tras el dato de inflación en Estados Unidos",
        "url": "https://www.eleconomista.com.mx/mercados/2026/08/20/peso-aprecia-inflacion-eu/",
        "source": "eleconomista.com.mx",
        "published_at": "2026-08-20T09:40:00-06:00",
        "summary": "La moneda mexicana ganó terreno frente al dólar después de que la inflación estadounidense resultó menor a lo previsto.",
        "topics": ["peso", "dólar", "tipo de cambio", "inflación"],
    },
    {
        "title": "Mexican stocks slip as investors weigh corporate earnings",
        "url": "https://www.reuters.com/markets/americas/mexican-stocks-slip-earnings-2026-08-26/",
        "source": "reuters.com",
        "published_at": "2026-08-26T16:10:00-06:00",
        "summary": "The S&P/BMV IPC fell for a third session as quarterly results disappointed in consumer and telecom names.",
        "topics": ["bolsa", "ipc", "acciones", "renta variable", "bmv"],
    },
    {
        "title": "Emisores corporativos colocan deuda a tasas más bajas",
        "url": "https://www.elfinanciero.com.mx/mercados/2026/08/22/emisores-corporativos-deuda-tasas/",
        "source": "elfinanciero.com.mx",
        "published_at": "2026-08-22T11:00:00-06:00",
        "summary": "Las colocaciones de deuda corporativa aprovecharon el ciclo de baja de tasas y redujeron sus costos de financiamiento.",
        "topics": ["deuda", "corporativa", "tasas", "emisores"],
    },
]

_RESEARCH: list[dict[str, Any]] = [
    {
        "title": "Perspectiva mensual: el ciclo de baja de tasas favorece la deuda de corto plazo",
        "url": "https://www.actinver.com/research/2026/08/perspectiva-mensual",
        "source": "Actinver Research",
        "published_at": "2026-08-28T08:00:00-06:00",
        "summary": "Mantenemos preferencia por deuda gubernamental de corto plazo y una posición neutral en renta variable local mientras se consolida el ciclo de recortes de Banxico.",
        "topics": ["tasas", "banxico", "deuda", "renta variable", "portafolio"],
    },
    {
        "title": "Renta variable local: revisión de estimados tras reportes del segundo trimestre",
        "url": "https://www.actinver.com/research/2026/08/renta-variable-2t",
        "source": "Actinver Research",
        "published_at": "2026-08-19T08:00:00-06:00",
        "summary": "Los reportes trimestrales mostraron márgenes presionados en consumo; ajustamos a la baja los estimados de utilidad para el año.",
        "topics": ["renta variable", "acciones", "reportes", "ipc", "bolsa"],
    },
    {
        "title": "Tipo de cambio: rangos esperados para el cierre de año",
        "url": "https://www.actinver.com/research/2026/08/tipo-de-cambio",
        "source": "Actinver Research",
        "published_at": "2026-08-25T08:00:00-06:00",
        "summary": "Esperamos un rango de operación acotado para el peso, con episodios de volatilidad ligados a la política monetaria de la Reserva Federal.",
        "topics": ["peso", "dólar", "tipo de cambio", "fed"],
    },
]


def _rank(items: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    terms = {t for t in query.lower().replace(",", " ").split() if len(t) > 2}
    scored = []
    for item in items:
        hay = " ".join([item["title"].lower(), item["summary"].lower(), *item["topics"]])
        score = sum(1 for t in terms if t in hay)
        scored.append((score, item))
    scored.sort(key=lambda s: (-s[0], s[1]["published_at"]), reverse=False)
    ranked = [i for score, i in scored if score > 0] or [i for _, i in scored]
    return [{k: v for k, v in i.items() if k != "topics"} for i in ranked[:limit]]


class SyntheticNews:
    async def search(self, **kw: Any) -> dict[str, Any]:
        if "news_down" in FAULTS:
            raise RuntimeError("news provider unavailable (fault injected)")
        return {
            "as_of": as_of(),
            "items": _rank(_NEWS, kw.get("query", ""), int(kw.get("limit") or 5)),
        }

    async def search_research(self, **kw: Any) -> dict[str, Any]:
        if "news_down" in FAULTS:
            raise RuntimeError("research corpus unavailable (fault injected)")
        return {
            "as_of": as_of(),
            "items": _rank(_RESEARCH, kw.get("query", ""), int(kw.get("limit") or 4)),
        }

    async def health(self) -> bool:
        return "news_down" not in FAULTS


# ── CRM and OMS ────────────────────────────────────────────────────────────────

_GUIDE_SECTIONS: dict[str, dict[str, str]] = {
    "servicios": {
        "title": "Servicios de inversión",
        "text": "Actinver ofrece servicios asesorados (asesoría de inversiones) y no asesorados "
        "(comercialización o promoción y ejecución de operaciones). El asistente digital "
        "opera conforme al servicio que tengas contratado.",
    },
    "comisiones": {
        "title": "Comisiones",
        "text": "Las comisiones aplicables a cada producto se detallan en su prospecto y en el "
        "documento con información clave para la inversión (DICI).",
    },
    "riesgos": {
        "title": "Riesgos",
        "text": "Toda inversión implica riesgos, incluida la pérdida del capital invertido. Los "
        "rendimientos pasados no garantizan rendimientos futuros.",
    },
    "reclamaciones": {
        "title": "Reclamaciones",
        "text": "Puedes presentar una reclamación ante la Unidad Especializada de Atención a Usuarios "
        "(UNE) y, en su caso, acudir a la CONDUSEF.",
    },
}


class SyntheticCrm:
    async def create_escalation(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        if "crm_down" in FAULTS:
            raise RuntimeError("CRM unavailable (fault injected)")
        client = CLIENTS.get(client_id, CLIENTS["cl_demo_moderado"])
        urgency = kw.get("urgency", "normal")
        sla = {"immediate": "30 minutos", "high": "2 horas", "normal": "el siguiente día hábil"}[
            urgency
        ]
        return {
            "as_of": as_of(),
            "case_id": f"case_{_stable_int(client_id, kw.get('summary_es', ''), str(now_mx().date()), mod=10**7):07d}",
            "sla": sla,
            "promotor_name": client["promotor"]["name"],
            "reason": kw.get("reason", "client_request"),
        }

    async def file_complaint(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        if "crm_down" in FAULTS:
            raise RuntimeError("CRM unavailable (fault injected)")
        deadline = (now_mx().date() + timedelta(days=30)).isoformat()
        return {
            "as_of": as_of(),
            "folio": f"UNE-{now_mx():%Y%m%d}-{_stable_int(client_id, kw.get('description_es', ''), mod=10**6):06d}",
            "category": kw.get("category", "otro"),
            "response_deadline": deadline,
            "condusef_notice": "Tienes derecho a acudir a la CONDUSEF si la respuesta no te satisface.",
        }

    async def get_services_guide(self, *, section: str = "completa") -> dict[str, Any]:
        if "crm_down" in FAULTS:
            raise RuntimeError("CMS unavailable (fault injected)")
        keys = list(_GUIDE_SECTIONS) if section == "completa" else [section]
        return {
            "as_of": as_of(),
            "version": "2026-06",
            "section": section,
            "sections": [{"id": k, **_GUIDE_SECTIONS[k]} for k in keys if k in _GUIDE_SECTIONS],
            "download_url": "https://documentos.actinver.local/guia-servicios-inversion-2026-06.pdf",
        }

    async def health(self) -> bool:
        return "crm_down" not in FAULTS


class SyntheticOms:
    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}

    async def place_order(
        self, *, client_id: str, order: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        if "oms_down" in FAULTS:
            raise RuntimeError("OMS unavailable (fault injected)")
        if idempotency_key in self._orders:
            return {**self._orders[idempotency_key], "idempotent_replay": True}
        order_id = f"ord_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]}"
        settlement = (now_mx().date() + timedelta(days=1)).isoformat()
        receipt = {
            "as_of": as_of(),
            "order_id": order_id,
            "client_id": client_id,
            "status": "RECEIVED",
            "settlement_date": settlement,
            "operation": order.get("operation"),
            "product_id": (order.get("product") or {}).get("id"),
            "amount": order.get("amount"),
        }
        self._orders[idempotency_key] = receipt
        return dict(receipt)

    async def health(self) -> bool:
        return "oms_down" not in FAULTS


def product_ids() -> list[str]:
    return list(PRODUCTS)


def demo_client_ids() -> list[str]:
    return list(CLIENTS)


def today_mx() -> date:
    return now_mx().date()
