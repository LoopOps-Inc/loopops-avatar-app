"""Escalation, complaints and disclosure documents.

``escalate_to_advisor`` and ``file_complaint`` create a CRM case / UNE folio.
Neither moves money or touches a position; they are the regulated hand-off and
complaint channels (DCGSI Art. 26, CONDUSEF), and they are also fired
automatically by the runtime on distress, repeated blocks and fraud mentions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from actinver_agent.ports import CrmPort
from actinver_agent.tools import results
from actinver_agent.tools.registry import ToolArgs, ToolRegistry, ToolSpec


class EscalateArgs(ToolArgs):
    reason: Literal[
        "client_request",
        "low_confidence",
        "out_of_scope",
        "guardrail_blocked",
        "distress",
        "complex_advisory",
        "fraud_report",
    ]
    summary_es: str = Field(
        max_length=1000, description="Resumen de la conversación para el asesor humano"
    )
    urgency: Literal["normal", "high", "immediate"] = "normal"


class ComplaintArgs(ToolArgs):
    category: Literal[
        "cargo_no_reconocido",
        "operacion_no_autorizada",
        "servicio",
        "informacion_incorrecta",
        "otro",
    ]
    description_es: str = Field(max_length=2000)


class GuideArgs(ToolArgs):
    section: Literal["servicios", "comisiones", "riesgos", "reclamaciones", "completa"] = "completa"


def register(registry: ToolRegistry, crm: CrmPort) -> None:
    registry.register(
        ToolSpec(
            name="escalate_to_advisor",
            description_es=(
                "Canaliza la conversación con el asesor humano del cliente, con un "
                "resumen del contexto. Úsala cuando el cliente lo pida, cuando no "
                "puedas responder con certeza, o cuando detectes molestia o urgencia."
            ),
            args_schema=EscalateArgs,
            fn=crm.create_escalation,
            classification="RESTRICTED",
            tags=("support",),
            result_model=results.EscalationResult,
        )
    )

    registry.register(
        ToolSpec(
            name="file_complaint",
            description_es=(
                "Registra una reclamación formal ante la Unidad Especializada de "
                "Atención a Usuarios (UNE) y devuelve el folio y los plazos de "
                "respuesta. Informa siempre al cliente de su derecho a acudir a "
                "CONDUSEF."
            ),
            args_schema=ComplaintArgs,
            fn=crm.file_complaint,
            classification="RESTRICTED",
            tags=("support", "condusef"),
            result_model=results.ComplaintResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_investment_services_guide",
            description_es=(
                "Devuelve la Guía de Servicios de Inversión vigente: servicios "
                "disponibles, sus diferencias, comisiones, riesgos y el "
                "procedimiento de reclamaciones."
            ),
            args_schema=GuideArgs,
            fn=crm.get_services_guide,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=86400,
            tags=("disclosure", "dcgsi"),
            result_model=results.GuideResult,
        )
    )
