"""Seed the four non-client collections with synthetic content
(docs/01-architecture/04 §3.2). Nothing here derives from a client record."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from actinver_agent.deps import Dependencies
from actinver_agent.retrieval.indexer import Indexer

log = structlog.get_logger(__name__)

RESEARCH_NOTES: list[dict[str, Any]] = [
    {
        "doc_id": "rn-2026-08-14-banxico",
        "title": "Banxico recorta la tasa de referencia 25 pb",
        "source": "Análisis Actinver",
        "published_at": datetime(2026, 8, 14, 15, 0, tzinfo=UTC),
        "text": (
            "El Banco de México redujo la tasa de referencia en 25 puntos base. La decisión favorece "
            "a los instrumentos de deuda gubernamental de corto plazo, cuyo precio sube cuando las "
            "tasas bajan. Para portafolios con una porción relevante en deuda, el efecto del mes "
            "fue positivo. La renta variable local mostró un desempeño mixto ante la volatilidad "
            "del tipo de cambio. Los rendimientos pasados no garantizan rendimientos futuros."
        ),
    },
    {
        "doc_id": "rn-2026-08-28-peso",
        "title": "Perspectiva del peso mexicano hacia el cierre de año",
        "source": "Análisis Actinver",
        "published_at": datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        "text": (
            "El peso se mantuvo estable frente al dólar en agosto, apoyado por el diferencial de "
            "tasas con Estados Unidos. Los escenarios del equipo de análisis contemplan volatilidad "
            "moderada alrededor de las decisiones de la Reserva Federal. Esta información es de "
            "carácter general y no constituye una recomendación personalizada."
        ),
    },
    {
        "doc_id": "rn-2026-07-30-renta-variable",
        "title": "Renta variable local: sectores con mejor desempeño relativo",
        "source": "Análisis Actinver",
        "published_at": datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
        "text": (
            "Durante el trimestre, los sectores de consumo básico y aeropuertos aportaron la mayor "
            "contribución al índice. Las emisoras industriales quedaron rezagadas por la "
            "incertidumbre comercial. La diversificación entre clases de activo sigue siendo la "
            "herramienta principal para administrar el riesgo del portafolio."
        ),
    },
]

PRODUCT_DOCS: list[dict[str, Any]] = [
    {
        "doc_id": "dici-ACTIGOB-BF",
        "title": "DICI ACTIGOB-BF - Actinver Gubernamental",
        "source": "Documento con Información Clave para la Inversión",
        "published_at": datetime(2026, 6, 1, tzinfo=UTC),
        "text": (
            "Fondo de deuda gubernamental de corto plazo en pesos. Objetivo: preservar el capital "
            "y ofrecer liquidez diaria invirtiendo en CETES, BONDES y reportos. Nivel de riesgo "
            "asignado por el comité: bajo. Comisión de administración anual 0.85 por ciento. "
            "Liquidez a 24 horas. Inversión mínima 10,000 pesos. Los rendimientos pasados no "
            "garantizan rendimientos futuros."
        ),
    },
    {
        "doc_id": "dici-ACTIVAR-RV",
        "title": "DICI ACTIVAR-RV - Actinver Renta Variable",
        "source": "Documento con Información Clave para la Inversión",
        "published_at": datetime(2026, 6, 1, tzinfo=UTC),
        "text": (
            "Fondo de renta variable local que replica una canasta de emisoras de la Bolsa "
            "Mexicana de Valores. Nivel de riesgo asignado por el comité: alto. Horizonte "
            "recomendado de largo plazo. Liquidez a 72 horas. El valor de la inversión puede "
            "aumentar o disminuir de manera significativa."
        ),
    },
]

POLICY_FAQ: list[dict[str, Any]] = [
    {
        "doc_id": "faq-horarios",
        "title": "Horarios de operación y cortes",
        "source": "Actinver - Preguntas frecuentes",
        "published_at": datetime(2026, 5, 1, tzinfo=UTC),
        "text": (
            "Las órdenes de compra y venta de fondos de inversión se reciben en días hábiles. El "
            "horario de corte para operar al precio del día es a las 13:30 horas, tiempo del centro "
            "de México. Las órdenes posteriores se procesan al siguiente día hábil. La liquidación "
            "depende del fondo y se muestra antes de confirmar cada operación."
        ),
    },
    {
        "doc_id": "faq-estado-cuenta",
        "title": "Estado de cuenta y comprobantes",
        "source": "Actinver - Preguntas frecuentes",
        "published_at": datetime(2026, 5, 1, tzinfo=UTC),
        "text": (
            "El estado de cuenta mensual está disponible en la aplicación dentro de los primeros "
            "cinco días hábiles de cada mes. Puedes descargarlo mediante un enlace seguro con "
            "vigencia limitada. Las comisiones aplicables se detallan en la Guía de Servicios de "
            "Inversión."
        ),
    },
]

REGULATORY_DISCLOSURES: list[dict[str, Any]] = [
    {
        "doc_id": "guia-servicios-2026-06",
        "title": "Guía de Servicios de Inversión (versión 2026-06)",
        "source": "Actinver - Guía de Servicios de Inversión",
        "published_at": datetime(2026, 6, 1, tzinfo=UTC),
        "text": (
            "Servicios de inversión asesorados: asesoría de inversiones y gestión de inversiones. "
            "Servicios no asesorados: comercialización o promoción y ejecución de operaciones. "
            "Antes de una recomendación personalizada se evalúa la razonabilidad entre el perfil "
            "del inversionista y el perfil del producto. Las reclamaciones se atienden en la Unidad "
            "Especializada de Atención a Usuarios y el cliente puede acudir a la CONDUSEF."
        ),
    },
]


async def seed_all(deps: Dependencies) -> int:
    from actinver_agent.retrieval.retriever import Retriever

    retriever: Retriever | None = getattr(deps, "retriever", None)
    if retriever is None:
        from actinver_agent.retrieval.retriever import MemoryVectorStore

        retriever = Retriever(deps.embedder, MemoryVectorStore())
    indexer = Indexer(deps.embedder, retriever.store)
    total = 0
    for collection, docs in (
        ("research_notes", RESEARCH_NOTES),
        ("product_docs", PRODUCT_DOCS),
        ("policy_faq", POLICY_FAQ),
        ("regulatory_disclosures", REGULATORY_DISCLOSURES),
    ):
        for doc in docs:
            total += await indexer.index_document(collection=collection, **doc)
    log.info("retrieval.seeded", chunks=total)
    return total
