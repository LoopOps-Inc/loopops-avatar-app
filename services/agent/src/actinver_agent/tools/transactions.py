"""Transactional planning tools.

**None of these mutate anything.** They return requirements and figures. The
signed FormSpec is built by ``transaction_planner``; execution happens only in
``transaction-service``, reached by an authenticated form submission carrying a
step-up assertion - never by a model-initiated call (ADR-0010).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field

from actinver_agent.ports import CoreBankingPort
from actinver_agent.tools import results
from actinver_agent.tools.registry import ToolArgs, ToolRegistry, ToolSpec

Operation = Literal["BUY", "SELL", "SWITCH", "REDEEM", "RECURRING"]


class RequirementsArgs(ToolArgs):
    product_id: str = Field(max_length=40, pattern=r"^[A-Z0-9\-]+$")
    operation: Operation
    amount: Decimal | None = Field(default=None, gt=0)
    target_product_id: str | None = Field(
        default=None, description="Sólo para SWITCH: producto destino"
    )


class SimulateArgs(ToolArgs):
    product_id: str = Field(max_length=40, pattern=r"^[A-Z0-9\-]+$")
    amount: Decimal = Field(gt=0)
    horizon_months: int = Field(ge=1, le=360)
    monthly_contribution: Decimal | None = Field(default=None, ge=0)


class FeesArgs(ToolArgs):
    product_id: str = Field(max_length=40, pattern=r"^[A-Z0-9\-]+$")
    operation: Operation
    amount: Decimal = Field(gt=0)
    holding_months: int | None = Field(default=None, ge=0, le=600)


def register(registry: ToolRegistry, core: CoreBankingPort) -> None:
    registry.register(
        ToolSpec(
            name="get_transaction_requirements",
            description_es=(
                "Devuelve TODO lo que se necesita para preparar una operación: "
                "campos requeridos, montos mínimo y máximo, hora de corte, fecha de "
                "liquidación, comisiones aplicables y las advertencias obligatorias. "
                "NO ejecuta la operación: sólo prepara el formulario que el cliente "
                "deberá confirmar."
            ),
            args_schema=RequirementsArgs,
            fn=core.get_transaction_requirements,
            classification="RESTRICTED",
            tags=("transaction", "planner"),
            result_model=results.RequirementsResult,
        )
    )

    registry.register(
        ToolSpec(
            name="simulate_investment",
            description_es=(
                "Proyecta escenarios de una inversión (pesimista, base, optimista) "
                "con base en la volatilidad histórica del producto. SIEMPRE es una "
                "simulación, nunca una promesa: menciónalo explícitamente."
            ),
            args_schema=SimulateArgs,
            fn=core.simulate_investment,
            requires_client=False,
            classification="PUBLIC",
            timeout_s=4.0,
            tags=("simulation",),
            result_model=results.SimulationResult,
        )
    )

    registry.register(
        ToolSpec(
            name="calculate_fees_and_taxes",
            description_es=(
                "Calcula comisiones aplicables y la retención de ISR estimada de una "
                "operación. La retención es estimada; el cálculo definitivo lo hace "
                "el área fiscal."
            ),
            args_schema=FeesArgs,
            fn=core.calculate_fees_and_taxes,
            classification="RESTRICTED",
            tags=("transaction", "tax"),
            result_model=results.FeesResult,
        )
    )
