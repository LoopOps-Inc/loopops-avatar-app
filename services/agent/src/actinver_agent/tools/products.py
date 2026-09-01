"""Investment product discovery and the suitability tool.

``check_suitability`` does not call the core. It assembles the evaluation
context (profile, committee profile, positions, committee limits) and calls
``suitability-service`` through the ``SuitabilityPort``. The verdict is binding:
the model may explain it but not qualify it (ADR-0005).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from actinver_agent.graph.state import InvestorProfile, ProductProfile
from actinver_agent.ports import CoreBankingPort, EvaluationInput, SuitabilityPort
from actinver_agent.tools import results
from actinver_agent.tools.registry import ToolArgs, ToolRegistry, ToolSpec


class ProductSearchArgs(ToolArgs):
    """Filters map onto the perfil del producto financiero (DCGSI Anexo 4)."""

    risk_level: list[Literal["bajo", "medio", "alto"]] | None = Field(
        default=None,
        description="Nivel de riesgo asignado por el comité de productos",
    )
    asset_class: list[str] | None = Field(
        default=None,
        description="deuda_gubernamental, deuda_corporativa, renta_variable_local, "
        "renta_variable_global, mixto, cobertura_cambiaria, alternativos",
    )
    horizon_months_max: int | None = Field(
        default=None, description="Plazo máximo de permanencia aceptable"
    )
    currency: Literal["MXN", "USD", "EUR"] | None = None
    liquidity_hours_max: int | None = Field(
        default=None, description="24, 48, 72 o nulo para no líquidos"
    )
    min_investment_max: Decimal | None = Field(
        default=None, description="Inversión mínima que el cliente puede cubrir"
    )
    limit: int = Field(default=8, le=20, ge=1)


class ProductIdArgs(ToolArgs):
    product_id: str = Field(max_length=40, pattern=r"^[A-Z0-9\-]+$")


class CompareArgs(ToolArgs):
    product_ids: list[str] = Field(min_length=2, max_length=4)


class SuitabilityArgs(ToolArgs):
    product_id: str = Field(max_length=40, pattern=r"^[A-Z0-9\-]+$")
    amount: Decimal = Field(gt=0, description="Monto en la divisa del producto")


def build_evaluation_input(
    *,
    amount: Decimal,
    positions: dict[str, Any],
    limits: dict[str, float],
    today: datetime | None = None,
) -> EvaluationInput:
    total = Decimal(positions["total_market_value"]["amount"])
    weights_product: dict[str, float] = {}
    weights_class: dict[str, float] = {}
    for position in positions.get("positions", []):
        weight = float(position["weight_pct"]) / 100
        weights_product[position["product_id"]] = weight
        weights_class[position["asset_class"]] = (
            weights_class.get(position["asset_class"], 0.0) + weight
        )
    return EvaluationInput(
        today=today or datetime.now(UTC),
        amount=amount,
        portfolio_total=total,
        current_weight_by_product=weights_product,
        current_weight_by_asset_class=weights_class,
        liquid_pct=float(positions.get("liquid_pct", 0.0)),
        diversification_limits=dict(limits),
    )


def make_check_suitability(
    core: CoreBankingPort, suitability: SuitabilityPort
) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def check_suitability(
        *, client_id: str, product_id: str, amount: Decimal
    ) -> dict[str, Any]:
        profile_raw = await core.get_investor_profile(client_id=client_id)
        profile = InvestorProfile.model_validate(
            {k: v for k, v in profile_raw.items() if k != "as_of"}
        )
        product_raw = await core.get_product_profile(product_id=product_id)
        product = ProductProfile.model_validate(
            {k: v for k, v in product_raw.items() if k != "as_of"}
        )
        positions = await core.get_positions(client_id=client_id)
        limits = await core.get_diversification_limits()
        ctx = build_evaluation_input(
            amount=Decimal(str(amount)), positions=positions, limits=limits
        )
        report = await suitability.evaluate(
            client_id=client_id, profile=profile, products=[product], ctx=ctx
        )
        return {
            "as_of": positions["as_of"],
            "verdict_id": report.verdict_id,
            "ruleset_version": report.ruleset_version,
            "evaluations": [e.model_dump(mode="json") for e in report.evaluations],
            "signature": report.signature,
        }

    return check_suitability


def register(registry: ToolRegistry, core: CoreBankingPort, suitability: SuitabilityPort) -> None:
    registry.register(
        ToolSpec(
            name="search_investment_products",
            description_es=(
                "Busca productos de inversión de Actinver por nivel de riesgo, clase "
                "de activo, plazo, divisa, liquidez e inversión mínima. Devuelve el "
                "perfil del producto asignado por el comité. NO determina si un "
                "producto es adecuado para el cliente: para eso usa check_suitability."
            ),
            args_schema=ProductSearchArgs,
            fn=core.search_products,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=3600,
            tags=("products",),
            result_model=results.ProductSearchResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_product_detail",
            description_es=(
                "Ficha completa de un producto: objetivo, política de inversión, "
                "comisiones, rendimientos históricos con su fecha, DICI y prospecto."
            ),
            args_schema=ProductIdArgs,
            fn=core.get_product_detail,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=3600,
            tags=("products",),
            result_model=results.ProductDetailResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_product_risk_profile",
            description_es=(
                "Perfil del producto financiero según el comité responsable del "
                "análisis de productos: riesgo, complejidad, costos, liquidez y "
                "cliente objetivo, con la versión del comité."
            ),
            args_schema=ProductIdArgs,
            fn=core.get_product_profile,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=3600,
            service_type="asesorado",
            tags=("products", "dcgsi"),
            result_model=results.ProductProfileResult,
        )
    )

    registry.register(
        ToolSpec(
            name="compare_products",
            description_es=(
                "Compara de 2 a 4 productos lado a lado en riesgo, plazo, comisiones, "
                "liquidez y rendimiento histórico."
            ),
            args_schema=CompareArgs,
            fn=core.compare_products,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=1800,
            tags=("products",),
            result_model=results.CompareResult,
        )
    )

    registry.register(
        ToolSpec(
            name="check_suitability",
            description_es=(
                "Evalúa la razonabilidad de un producto para ESTE cliente contra su "
                "perfil del inversionista, conforme a la normativa aplicable. "
                "Devuelve APTO, APTO_CON_ADVERTENCIA o NO_APTO con el motivo. "
                "Es OBLIGATORIA antes de sugerir cualquier producto en particular. "
                "El veredicto es determinante: no lo interpretes ni lo matices."
            ),
            args_schema=SuitabilityArgs,
            fn=make_check_suitability(core, suitability),
            classification="RESTRICTED",
            service_type="asesorado",
            timeout_s=4.0,
            tags=("suitability", "dcgsi"),
            result_model=results.SuitabilityResult,
        )
    )
