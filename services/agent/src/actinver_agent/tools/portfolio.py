"""Portfolio and client tools. All read-only, all client-scoped by injection."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from actinver_agent.ports import CoreBankingPort
from actinver_agent.tools import results
from actinver_agent.tools.registry import ToolArgs, ToolRegistry, ToolSpec


class NoArgs(ToolArgs):
    pass


class PerformanceArgs(ToolArgs):
    period: Literal["MTD", "QTD", "YTD", "1Y", "3Y", "SINCE_INCEPTION"] = Field(
        default="MTD", description="Periodo de medición del rendimiento"
    )


class AttributionArgs(ToolArgs):
    period: Literal["MTD", "QTD", "YTD", "1Y"] = "MTD"
    granularity: Literal["asset_class", "product", "currency"] = "asset_class"


class HistoryArgs(ToolArgs):
    since: date | None = Field(default=None, description="Fecha inicial")
    until: date | None = None
    operation_type: Literal["ALL", "BUY", "SELL", "DIVIDEND", "FEE"] = "ALL"
    limit: int = Field(default=20, le=100, ge=1)


class StatementArgs(ToolArgs):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


def register(registry: ToolRegistry, core: CoreBankingPort) -> None:
    registry.register(
        ToolSpec(
            name="get_investor_profile",
            description_es=(
                "Obtiene el perfil del inversionista vigente del cliente: categoría "
                "de riesgo, horizonte, nivel de conocimiento, objetivos y vigencia. "
                "Úsala antes de cualquier recomendación."
            ),
            args_schema=NoArgs,
            fn=core.get_investor_profile,
            classification="RESTRICTED",
            cache_ttl_s=300,
            service_type="asesorado",
            tags=("profile", "dcgsi"),
            result_model=results.InvestorProfileResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_portfolio_positions",
            description_es=(
                "Devuelve las posiciones actuales del cliente: instrumento, "
                "cantidad, valor de mercado, costo promedio y peso en el portafolio. "
                "Los importes exactos se muestran en pantalla, no se pronuncian."
            ),
            args_schema=NoArgs,
            fn=core.get_positions,
            classification="RESTRICTED",
            cache_ttl_s=60,
            tags=("portfolio",),
            result_model=results.PositionsResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_portfolio_performance",
            description_es=(
                "Rendimiento del portafolio en el periodo solicitado, en porcentaje "
                "y en importe, con la fecha de valuación."
            ),
            args_schema=PerformanceArgs,
            fn=core.get_performance,
            classification="RESTRICTED",
            cache_ttl_s=60,
            tags=("portfolio",),
            result_model=results.PerformanceResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_portfolio_attribution",
            description_es=(
                "Explica POR QUÉ se movió el portafolio: descompone el rendimiento "
                "del periodo por clase de activo, producto o divisa, en puntos base. "
                "Es la herramienta principal para responder '¿por qué subió/bajó?'."
            ),
            args_schema=AttributionArgs,
            fn=core.get_attribution,
            classification="RESTRICTED",
            cache_ttl_s=60,
            timeout_s=4.0,
            tags=("portfolio", "explain"),
            result_model=results.AttributionResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_cash_balance",
            description_es="Efectivo disponible y por liquidar, con fechas de liquidación.",
            args_schema=NoArgs,
            fn=core.get_cash_balance,
            classification="RESTRICTED",
            cache_ttl_s=30,
            tags=("portfolio",),
            result_model=results.CashResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_client_accounts",
            description_es="Cuentas del cliente elegibles para cargo o abono.",
            args_schema=NoArgs,
            fn=core.get_accounts,
            classification="RESTRICTED",
            cache_ttl_s=300,
            tags=("accounts",),
            result_model=results.AccountsResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_transaction_history",
            description_es="Historial de operaciones del cliente con filtros por fecha y tipo.",
            args_schema=HistoryArgs,
            fn=core.get_transaction_history,
            classification="RESTRICTED",
            cache_ttl_s=60,
            tags=("history",),
            result_model=results.HistoryResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_account_statements",
            description_es="Estado de cuenta del periodo solicitado (enlace seguro).",
            args_schema=StatementArgs,
            fn=core.get_statement,
            classification="RESTRICTED",
            cache_ttl_s=3600,
            tags=("documents",),
            result_model=results.StatementResult,
        )
    )
