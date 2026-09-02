"""InvestmentOffice tools registration for LangGraph and Gemini.

Registers the 11 read-only tools defined in the InvestmentOffice Tool Layer:
H01 · listar_contratos
H02 · obtener_posicion_total
H03 · obtener_posiciones
H04 · obtener_saldos_por_producto
H05 · obtener_vencimientos
H06 · obtener_polizas
H07 · obtener_creditos
H08 · obtener_movimientos
H09 · obtener_asesor
H10 · obtener_resumen_inicial
H11 · escalar_a_asesor
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncEngine

from actinver_agent.clients.investment_office_sql import InvestmentOfficeSqlCore
from actinver_agent.tools.registry import ToolArgs, ToolRegistry, ToolSpec

# ── Argument Schemas ──────────────────────────────────────────────────────────


class NoArgs(ToolArgs):
    pass


class ListarContratosArgs(ToolArgs):
    tipo: Literal["INVERSION", "CREDITO", "RETIRO"] | None = Field(
        default=None, description="Filtro opcional por tipo de contrato"
    )


class ObtenerPosicionesArgs(ToolArgs):
    instrumento: Literal["ACCION", "ETF", "FONDO", "BONO"] | None = Field(
        default=None, description="Tipo de instrumento financiero"
    )
    tipo_producto: Literal["RV", "RF"] | None = Field(
        default=None, description="Renta Variable (RV) o Renta Fija (RF)"
    )
    emisora: str | None = Field(
        default=None, description="Clave de pizarra o emisora (ej. BIMBO, FEMSA, WALMEX)"
    )
    limite: int = Field(
        default=15, ge=1, le=100, description="Cantidad máxima de posiciones a devolver"
    )


class ObtenerSaldosPorProductoArgs(ToolArgs):
    producto: Literal["FONDOS", "CEDE", "PRLV", "MANDATOS", "PPR", "FONDOS_COMPLEJOS"] | None = (
        Field(default=None, description="Línea de producto específica a consultar")
    )


class ObtenerVencimientosArgs(ToolArgs):
    producto: Literal["POSICION", "CEDE", "PRLV", "CREDITO"] | None = Field(
        default=None, description="Tipo de producto para consulta de vencimiento"
    )


class ObtenerPolizasArgs(ToolArgs):
    ramo: Literal["VIDA", "GMM", "AUTO"] | None = Field(
        default=None, description="Ramo de seguro a consultar"
    )


class ObtenerMovimientosArgs(ToolArgs):
    desde: date = Field(default=date(2023, 1, 1), description="Fecha inicial (cobertura 2023)")
    hasta: date = Field(default=date(2023, 12, 31), description="Fecha final (cobertura 2023)")
    tipo: Literal["ABONO", "CARGO"] | None = Field(
        default=None, description="Tipo de movimiento (ABONO / CARGO)"
    )
    incluir_traspasos: bool = Field(
        default=True, description="Incluir traspasos además de transacciones"
    )
    limite: int = Field(default=10, ge=1, le=50, description="Máximo de movimientos a listar")


class EscalarAsesorArgs(ToolArgs):
    motivo: Literal[
        "dato_no_disponible",
        "fuera_de_alcance",
        "solicita_asesoria",
        "desempeno_o_causa",
        "operacion_requerida",
        "cliente_lo_pide",
    ] = Field(description="Causa por la que se deriva la atención al asesor humano")
    detalle: str = Field(description="Pregunta original o requerimiento del cliente")


# ── Tool Registration ─────────────────────────────────────────────────────────


def register_investment_office_tools(
    registry: ToolRegistry,
    engine: AsyncEngine,
    sql_core: InvestmentOfficeSqlCore | None = None,
) -> None:
    core = sql_core or InvestmentOfficeSqlCore(engine)

    async def _resolve_client(conn: Any, client_id: str | None) -> int:
        return await core.resolve_id_cliente(conn, client_id or "1")

    # H01: listar_contratos
    async def fn_listar_contratos(client_id: str | None, tipo: Any = None) -> list[dict[str, Any]]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.listar_contratos(conn, id_cliente=cid, tipo=tipo)

    registry.register(
        ToolSpec(
            name="listar_contratos",
            description_es="Lista los contratos activos del cliente clasificados por tipo y unidad de negocio.",
            args_schema=ListarContratosArgs,
            fn=fn_listar_contratos,
            classification="RESTRICTED",
            cache_ttl_s=300,
            tags=("investment_office", "contracts"),
        )
    )

    # H02: obtener_posicion_total
    async def fn_obtener_posicion_total(client_id: str | None) -> dict[str, Any]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_posicion_total(conn, id_cliente=cid)

    registry.register(
        ToolSpec(
            name="obtener_posicion_total",
            description_es="Calcula la posición total de inversión al último corte de valuación por contrato.",
            args_schema=NoArgs,
            fn=fn_obtener_posicion_total,
            classification="RESTRICTED",
            cache_ttl_s=60,
            tags=("investment_office", "portfolio"),
        )
    )

    # H03: obtener_posiciones
    async def fn_obtener_posiciones(
        client_id: str | None,
        instrumento: Any = None,
        tipo_producto: Any = None,
        emisora: Any = None,
        limite: int = 15,
    ) -> list[dict[str, Any]]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_posiciones(
                conn,
                id_cliente=cid,
                instrumento=instrumento,
                tipo_producto=tipo_producto,
                emisora=emisora,
                limite=limite,
            )

    registry.register(
        ToolSpec(
            name="obtener_posiciones",
            description_es=(
                "Lista las posiciones detalladas del cliente (acciones, fondos, ETFs, bonos) con "
                "títulos y precio de cierre."
            ),
            args_schema=ObtenerPosicionesArgs,
            fn=fn_obtener_posiciones,
            classification="RESTRICTED",
            cache_ttl_s=60,
            tags=("investment_office", "portfolio"),
        )
    )

    # H04: obtener_saldos_por_producto
    async def fn_obtener_saldos_por_producto(
        client_id: str | None, producto: Any = None
    ) -> list[dict[str, Any]]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_saldos_por_producto(conn, id_cliente=cid, producto=producto)

    registry.register(
        ToolSpec(
            name="obtener_saldos_por_producto",
            description_es=(
                "Obtiene la distribución patrimonial por producto (PPR, mandatos, CEDEs, PRLVs, fondos) "
                "con su respectiva naturaleza (SALDO, CAPITAL_INICIAL o FLUJO_NETO)."
            ),
            args_schema=ObtenerSaldosPorProductoArgs,
            fn=fn_obtener_saldos_por_producto,
            classification="RESTRICTED",
            cache_ttl_s=120,
            tags=("investment_office", "balances"),
        )
    )

    # H05: obtener_vencimientos
    async def fn_obtener_vencimientos(
        client_id: str | None, producto: Any = None
    ) -> dict[str, Any]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_vencimientos(conn, id_cliente=cid, producto=producto)

    registry.register(
        ToolSpec(
            name="obtener_vencimientos",
            description_es="Consulta los vencimientos reales de instrumentos o genera la derivación al asesor si el dato no está registrado.",
            args_schema=ObtenerVencimientosArgs,
            fn=fn_obtener_vencimientos,
            classification="RESTRICTED",
            cache_ttl_s=300,
            tags=("investment_office", "maturities"),
        )
    )

    # H06: obtener_polizas
    async def fn_obtener_polizas(client_id: str | None, ramo: Any = None) -> list[dict[str, Any]]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_polizas(conn, id_cliente=cid, ramo=ramo)

    registry.register(
        ToolSpec(
            name="obtener_polizas",
            description_es="Consulta las pólizas de seguro activas y su estatus de cobranza y vigencia.",
            args_schema=ObtenerPolizasArgs,
            fn=fn_obtener_polizas,
            classification="RESTRICTED",
            cache_ttl_s=300,
            tags=("investment_office", "insurance"),
        )
    )

    # H07: obtener_creditos
    async def fn_obtener_creditos(client_id: str | None) -> list[dict[str, Any]]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_creditos(conn, id_cliente=cid)

    registry.register(
        ToolSpec(
            name="obtener_creditos",
            description_es="Obtiene el saldo insoluto actual y estatus de pago de los créditos activos del cliente.",
            args_schema=NoArgs,
            fn=fn_obtener_creditos,
            classification="RESTRICTED",
            cache_ttl_s=120,
            tags=("investment_office", "credits"),
        )
    )

    # H08: obtener_movimientos
    async def fn_obtener_movimientos(
        client_id: str | None,
        desde: date = date(2023, 1, 1),
        hasta: date = date(2023, 12, 31),
        tipo: Any = None,
        incluir_traspasos: bool = True,
        limite: int = 10,
    ) -> dict[str, Any]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_movimientos(
                conn,
                id_cliente=cid,
                desde=desde,
                hasta=hasta,
                tipo=tipo,
                incluir_traspasos=incluir_traspasos,
                limite=limite,
            )

    registry.register(
        ToolSpec(
            name="obtener_movimientos",
            description_es="Consulta el historial de transacciones y traspasos registrados (ventana de cobertura 2023).",
            args_schema=ObtenerMovimientosArgs,
            fn=fn_obtener_movimientos,
            classification="RESTRICTED",
            cache_ttl_s=120,
            tags=("investment_office", "movements"),
        )
    )

    # H09: obtener_asesor
    async def fn_obtener_asesor(client_id: str | None) -> list[dict[str, Any]]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_asesor(conn, id_cliente=cid)

    registry.register(
        ToolSpec(
            name="obtener_asesor",
            description_es="Obtiene los datos del asesor patrimonial asignado, su centro financiero y puesto.",
            args_schema=NoArgs,
            fn=fn_obtener_asesor,
            classification="RESTRICTED",
            cache_ttl_s=600,
            tags=("investment_office", "advisor"),
        )
    )

    # H10: obtener_resumen_inicial
    async def fn_obtener_resumen_inicial(client_id: str | None) -> dict[str, Any]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.obtener_resumen_inicial(conn, id_cliente=cid)

    registry.register(
        ToolSpec(
            name="obtener_resumen_inicial",
            description_es="Precarga inicial de contratos, posición total, créditos y asesor al inicio de sesión.",
            args_schema=NoArgs,
            fn=fn_obtener_resumen_inicial,
            classification="RESTRICTED",
            cache_ttl_s=300,
            tags=("investment_office", "prefetch"),
        )
    )

    # H11: escalar_a_asesor
    async def fn_escalar_a_asesor(
        client_id: str | None,
        motivo: Any,
        detalle: str,
    ) -> dict[str, Any]:
        async with engine.connect() as conn:
            cid = await _resolve_client(conn, client_id)
            return await core.escalar_a_asesor(conn, id_cliente=cid, motivo=motivo, detalle=detalle)

    registry.register(
        ToolSpec(
            name="escalar_a_asesor",
            description_es=(
                "Canaliza al asesor financiero humano ante preguntas de rendimiento, causas de movimiento, "
                "solicitud expresa o datos no disponibles."
            ),
            args_schema=EscalarAsesorArgs,
            fn=fn_escalar_a_asesor,
            classification="RESTRICTED",
            cache_ttl_s=0,
            tags=("investment_office", "escalation"),
        )
    )
