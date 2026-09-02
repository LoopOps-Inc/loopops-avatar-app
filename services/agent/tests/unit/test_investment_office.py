"""Unit tests for InvestmentOffice SQL client and 11 tools.

Tests the 11 tools and asserts the 6 data traps (T1-T6):
T1: baja_logica IS NOT TRUE handles NULL baja_logica in mandatos.
T2: MAX(snapshot_date) per contract and valuacion_mixta flag.
T3: saldo_vencido NULL is mapped to 'no_informado', never '0.00'.
T4: naturaleza tag distinguishes SALDO, CAPITAL_INICIAL and FLUJO_NETO.
T5: precio is not projected into positions.
T6: inv_seguros filters by id_cliente_fk directly.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from actinver_agent.clients.investment_office_sql import InvestmentOfficeSqlCore
from actinver_agent.tools.investment_office import register_investment_office_tools
from actinver_agent.tools.registry import ToolRegistry


class SqliteMappingsResult:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class SqliteQueryResult:
    def __init__(self, rows: list[dict[str, Any]], scalar_val: Any = None):
        self._rows = rows
        self._scalar_val = scalar_val

    def mappings(self) -> SqliteMappingsResult:
        return SqliteMappingsResult(self._rows)

    def scalar_one_or_none(self) -> Any:
        return self._scalar_val


class AsyncSqliteAdapter:
    """Async wrapper around standard library sqlite3 for unit testing without extra drivers."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    async def execute(self, query: Any, params: dict[str, Any] | None = None) -> SqliteQueryResult:
        q_str = str(query)

        # SQLite query adaptations for postgres-specific syntax:
        q_str = q_str.replace("public.", "").replace("::date", "").replace("::text", "")
        q_str = q_str.replace("IS TRUE", "= 1").replace("IS NOT TRUE", "IS NOT 1")
        if "ARRAY_AGG" in q_str:
            q_str = re.sub(r"ARRAY_AGG\((.*?)\)", r"GROUP_CONCAT(\1)", q_str)
            q_str = q_str.replace(" ORDER BY c.num_contrato", "")

        def _run() -> SqliteQueryResult:
            cur = self._db.cursor()
            p = params or {}
            # Replace True/False in p with 1/0 for sqlite
            sqlite_p = {k: (1 if v is True else 0 if v is False else v) for k, v in p.items()}
            cur.execute(q_str, sqlite_p)
            if cur.description:
                cols = [desc[0] for desc in cur.description]
                fetched = cur.fetchall()
                rows = []
                for row in fetched:
                    d = dict(zip(cols, row, strict=False))
                    if "contratos" in d and isinstance(d["contratos"], str):
                        d["contratos"] = [int(x) for x in d["contratos"].split(",") if x]
                    rows.append(d)
                scalar_val = fetched[0][0] if fetched else None
                return SqliteQueryResult(rows, scalar_val)
            return SqliteQueryResult([])

        return await asyncio.to_thread(_run)


class AsyncSqliteEngine:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def connect(self):
        class _Ctx:
            def __init__(self, db):
                self._conn = AsyncSqliteAdapter(db)

            async def __aenter__(self):
                return self._conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return _Ctx(self._db)


@pytest.fixture
def io_sqlite():
    """Create an in-memory SQLite connection populated with InvestmentOffice tables."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Create schema
    cur.executescript("""
        CREATE TABLE inv_cat_perfil_inversion (
            id_perfil_inv_pk INTEGER PRIMARY KEY,
            nombre_perfil TEXT,
            descripcion_perfil TEXT
        );
        CREATE TABLE inv_cat_centro_financiero (
            id_centro_financiero_pk INTEGER PRIMARY KEY,
            desc_centro_financiero TEXT,
            baja_logica BOOLEAN DEFAULT 0
        );
        CREATE TABLE inv_cat_banca (
            id_banca_pk INTEGER PRIMARY KEY,
            desc_banca TEXT,
            baja_logica BOOLEAN DEFAULT 0
        );
        CREATE TABLE inv_cat_puesto (
            id_puesto_pk INTEGER PRIMARY KEY,
            desc_puesto TEXT,
            baja_logica BOOLEAN DEFAULT 0
        );
        CREATE TABLE inv_asesor (
            id_asesor_pk INTEGER PRIMARY KEY,
            num_asesor INTEGER,
            nombre_completo TEXT,
            correo_electronico TEXT,
            current_flag BOOLEAN DEFAULT 1,
            baja_logica BOOLEAN DEFAULT 0,
            id_centro_financiero_fk INTEGER,
            id_banca_fk INTEGER,
            id_puesto_fk INTEGER
        );
        CREATE TABLE inv_cliente (
            id_cliente_pk INTEGER PRIMARY KEY,
            numero_cliente_unico INTEGER,
            nombre TEXT,
            apellido_paterno TEXT,
            apellido_materno TEXT,
            rfc TEXT,
            correo_electronico TEXT,
            id_perfil_inv_fk INTEGER,
            baja_logica BOOLEAN DEFAULT 0
        );
        CREATE TABLE inv_contrato (
            id_contrato_pk INTEGER PRIMARY KEY,
            num_contrato INTEGER,
            tipo_contrato TEXT,
            subtipo_contrato TEXT,
            desc_unidad_negocio TEXT,
            fecha_apertura DATE,
            estatus_contrato TEXT,
            current_flag BOOLEAN DEFAULT 1,
            baja_logica BOOLEAN DEFAULT 0,
            id_cliente_fk INTEGER,
            id_asesor_fk INTEGER
        );
        CREATE TABLE inv_posicion_inversion (
            id_posicion_pk INTEGER PRIMARY KEY,
            desc_instrumento TEXT,
            desc_tipo_producto TEXT,
            clave_emisora TEXT,
            desc_emisora TEXT,
            serie TEXT,
            cantidad_titulos NUMERIC,
            precio NUMERIC,
            precio_cierre NUMERIC,
            posicion_total NUMERIC,
            fecha_vencimiento DATE,
            plazo NUMERIC,
            snapshot_date DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_ppr (
            id_ppr_pk INTEGER PRIMARY KEY,
            subtipo_contrato TEXT,
            monto_posicion NUMERIC,
            snapshot_date DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_nnf_det_mandatos (
            id_mandato_pk INTEGER PRIMARY KEY,
            importe NUMERIC,
            snapshot_date DATE,
            baja_logica BOOLEAN, -- NULL in real dump (Trap T1)
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_nnf_det_cede (
            id_cede_pk INTEGER PRIMARY KEY,
            capital_inicial NUMERIC,
            fecha_apertura DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_nnf_prlv (
            id_prlv_pk INTEGER PRIMARY KEY,
            capital_inicial NUMERIC,
            fecha_apertura DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_nnf_det_fondos (
            id_fondos_pk INTEGER PRIMARY KEY,
            tipo_operacion TEXT,
            importe NUMERIC,
            fecha_operacion DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_nna_fondos_complejos (
            id_fc_pk INTEGER PRIMARY KEY,
            tipo_movimiento TEXT,
            monto_mxn NUMERIC,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_seguros (
            id_seguro_pk INTEGER PRIMARY KEY,
            numero_poliza TEXT,
            ramo TEXT,
            subramo TEXT,
            prima_neta NUMERIC,
            prima_total NUMERIC,
            estatus_cobranza TEXT,
            estatus_poliza TEXT,
            snapshot_date DATE,
            fecha_inicio_vigencia DATE,
            fecha_fin_vigencia DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_cliente_fk INTEGER
        );
        CREATE TABLE inv_creditos (
            id_credito_pk INTEGER PRIMARY KEY,
            num_credito_sistema TEXT,
            tipo_credito TEXT,
            monto_original NUMERIC,
            saldo_insoluto_actual NUMERIC,
            saldo_vencido NUMERIC, -- NULL in dump (Trap T3)
            estatus_pago TEXT,
            fecha_vencimiento DATE, -- NULL in dump
            snapshot_date DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_nna_det_transacciones (
            id_transaccion_pk INTEGER PRIMARY KEY,
            desc_transaccion TEXT,
            tipo_movimiento TEXT,
            nombre_divisa TEXT,
            importe_mxn NUMERIC,
            snapshot_date DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );
        CREATE TABLE inv_nna_det_traspasos (
            id_traspaso_pk INTEGER PRIMARY KEY,
            desc_transaccion TEXT,
            tipo_movimiento TEXT,
            nombre_divisa TEXT,
            importe_mxn NUMERIC,
            snapshot_date DATE,
            baja_logica BOOLEAN DEFAULT 0,
            id_contrato_fk INTEGER
        );

        -- Seed Client 1
        INSERT INTO inv_cat_perfil_inversion VALUES (3, 'Agresivo', 'Alto apetito por riesgo');
        INSERT INTO inv_cat_centro_financiero VALUES (1, 'CF Reforma CDMX', 0);
        INSERT INTO inv_cat_banca VALUES (1, 'Banca Patrimonial y Privada', 0);
        INSERT INTO inv_cat_puesto VALUES (1, 'Banquer@ Patrimonial', 0);
        INSERT INTO inv_asesor VALUES (1, 1001, 'Alberto Hernán Guevara', 'alberto@actinver.com', 1, 0, 1, 1, 1);
        INSERT INTO inv_cliente VALUES (1, 200001, 'Mariano', 'Gonzales', 'Santiago', 'DAXI800214FE8', 'mariano@gmail.com', 3, 0);

        INSERT INTO inv_contrato VALUES (1, 10001, 'INVERSION', 'BURSANET', 'PATRIMONIAL', '2020-01-01', 'ACTIVO', 1, 0, 1, 1);
        INSERT INTO inv_contrato VALUES (2, 10002, 'INVERSION', 'ALPHA', 'PATRIMONIAL', '2020-01-01', 'ACTIVO', 1, 0, 1, 1);
        INSERT INTO inv_contrato VALUES (3, 10003, 'CREDITO', 'CREDITO', 'PATRIMONIAL', '2020-01-01', 'ACTIVO', 1, 0, 1, 1);
        INSERT INTO inv_contrato VALUES (4, 10004, 'RETIRO', 'PPR', 'PATRIMONIAL', '2020-01-01', 'ACTIVO', 1, 0, 1, 1);

        INSERT INTO inv_posicion_inversion VALUES (1, 'ACCION', 'RV', 'BIMBO', 'GRUPO BIMBO', 'A', 5000, 65.5, 70.0, 350000.0, NULL, NULL, '2023-03-31', 0, 1);
        INSERT INTO inv_posicion_inversion VALUES (2, 'ACCION', 'RV', 'FEMSA', 'FEMSA UBD', 'UBD', 1200, 160.0, 175.0, 210000.0, NULL, NULL, '2023-03-31', 0, 1);
        INSERT INTO inv_posicion_inversion VALUES (3, 'BONO', 'RF', 'ZONALCB', 'INBURSA', '06-3U', 5000, 100.0, 101.25, 506250.0, '2026-03-15', 1826, '2023-03-31', 0, 1);
        INSERT INTO inv_posicion_inversion VALUES (4, 'FONDO', 'RV', 'ACTIAI', 'ACTINVER AI', 'B', 75000, 93.0, 100.0, 7500000.0, NULL, NULL, '2024-03-31', 0, 2);

        INSERT INTO inv_ppr VALUES (1, 'PPR INDIVIDUAL', 350000.0, '2023-03-31', 0, 4);
        INSERT INTO inv_nnf_det_mandatos VALUES (1, 1200000.0, '2023-03-31', NULL, 2);
        INSERT INTO inv_nnf_det_cede VALUES (1, 500000.0, '2023-01-15', 0, 2);
        INSERT INTO inv_nnf_prlv VALUES (1, 300000.0, '2023-02-10', 0, 2);
        INSERT INTO inv_nnf_det_fondos VALUES (1, 'COMPRA', 200000.0, '2023-04-01', 0, 2);
        INSERT INTO inv_nnf_det_fondos VALUES (2, 'VENTA', 50000.0, '2023-05-15', 0, 2);
        INSERT INTO inv_seguros VALUES (1, 'POL-VIDA-001', 'VIDA', 'VIDA INDIVIDUAL', 15000.0, 17400.0, 'PAGADA', 'ACTIVA', '2023-03-31', NULL, NULL, 0, 1);
        INSERT INTO inv_creditos VALUES (1, 'CR-HIPO-901', 'HIPOTECARIO', 2500000.0, 1850000.0, NULL, 'AL CORRIENTE', NULL, '2023-03-31', 0, 3);
        INSERT INTO inv_nna_det_transacciones VALUES (1, 'DEPOSITO SPEI', 'ABONO', 'MXN', 100000.0, '2023-06-15', 0, 1);
        INSERT INTO inv_nna_det_traspasos VALUES (1, 'TRASPASO ENTRE CUENTAS', 'CARGO', 'MXN', 20000.0, '2023-07-20', 0, 2);
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def async_adapter(io_sqlite):
    return AsyncSqliteAdapter(io_sqlite)


@pytest.mark.asyncio
async def test_io_client_discovery(async_adapter):
    core = InvestmentOfficeSqlCore()
    investors = await core.list_investors(async_adapter)
    assert len(investors) == 1
    inv = investors[0]
    assert inv["id_cliente_pk"] == 1
    assert inv["numero_cliente_unico"] == 200001
    assert inv["nombre_completo"] == "Mariano Gonzales Santiago"
    assert inv["perfil_riesgo"] == "Agresivo"
    assert inv["total_contratos"] == 4


@pytest.mark.asyncio
async def test_h01_listar_contratos(async_adapter):
    core = InvestmentOfficeSqlCore()
    all_contracts = await core.listar_contratos(async_adapter, id_cliente=1)
    assert len(all_contracts) == 4
    inversion = await core.listar_contratos(async_adapter, id_cliente=1, tipo="INVERSION")
    assert len(inversion) == 2


@pytest.mark.asyncio
async def test_h02_obtener_posicion_total_trap_t2(async_adapter):
    """Assert Trap T2: handles two valuation dates and flags valuacion_mixta."""
    core = InvestmentOfficeSqlCore()
    res = await core.obtener_posicion_total(async_adapter, id_cliente=1)
    assert len(res["por_contrato"]) == 2
    assert res["valuacion_mixta"] is True
    assert len(res["fechas_valuacion"]) == 2
    assert Decimal(res["total_mxn"]) == Decimal("8566250.0")


@pytest.mark.asyncio
async def test_h03_obtener_posiciones_trap_t5(async_adapter):
    """Assert Trap T5: precio is not projected, only precio_cierre and posicion_total."""
    core = InvestmentOfficeSqlCore()
    positions = await core.obtener_posiciones(async_adapter, id_cliente=1, instrumento="ACCION")
    assert len(positions) == 2
    p0 = positions[0]
    assert "precio" not in p0
    assert p0["clave_emisora"] in ("BIMBO", "FEMSA")
    assert p0["precio_cierre"] is not None
    assert p0["posicion_total"] is not None


@pytest.mark.asyncio
async def test_h04_obtener_saldos_por_producto_traps_t1_t4(async_adapter):
    """Assert Trap T1 (NULL baja_logica on mandatos) and T4 (naturaleza tags)."""
    core = InvestmentOfficeSqlCore()
    saldos = await core.obtener_saldos_por_producto(async_adapter, id_cliente=1)
    by_prod = {s["producto"]: s for s in saldos}

    # Trap T1: Mandato returned despite NULL baja_logica
    assert "MANDATOS" in by_prod
    assert by_prod["MANDATOS"]["naturaleza"] == "SALDO"
    assert Decimal(by_prod["MANDATOS"]["monto_mxn"]) == Decimal("1200000.0")

    # Trap T4: Naturalezas
    assert by_prod["PPR"]["naturaleza"] == "SALDO"
    assert by_prod["CEDE"]["naturaleza"] == "CAPITAL_INICIAL"
    assert by_prod["PRLV"]["naturaleza"] == "CAPITAL_INICIAL"
    assert by_prod["FONDOS"]["naturaleza"] == "FLUJO_NETO"
    assert Decimal(by_prod["FONDOS"]["monto_mxn"]) == Decimal("150000.0")


@pytest.mark.asyncio
async def test_h05_obtener_vencimientos_refusals(async_adapter):
    """Assert H05 returns structured refusals for CEDE/PRLV/CREDITO without inventing dates."""
    core = InvestmentOfficeSqlCore()
    res = await core.obtener_vencimientos(async_adapter, id_cliente=1)
    assert len(res["disponibles"]) == 1
    assert res["disponibles"][0]["clave_emisora"] == "ZONALCB"
    assert res["disponibles"][0]["fecha_vencimiento"] == "2026-03-15"

    refusals = {n["producto"]: n for n in res["no_disponibles"]}
    assert "CEDE" in refusals
    assert refusals["CEDE"]["disponible"] is False
    assert refusals["CEDE"]["accion_sugerida"] == "escalar_a_asesor"


@pytest.mark.asyncio
async def test_h06_obtener_polizas_trap_t6(async_adapter):
    """Assert Trap T6: policies join directly on id_cliente_fk."""
    core = InvestmentOfficeSqlCore()
    polizas = await core.obtener_polizas(async_adapter, id_cliente=1)
    assert len(polizas) == 1
    pol = polizas[0]
    assert pol["numero_poliza"] == "POL-VIDA-001"
    assert pol["estatus_cobranza"] == "PAGADA"
    assert pol["vigencia_disponible"] is False


@pytest.mark.asyncio
async def test_h07_obtener_creditos_trap_t3(async_adapter):
    """Assert Trap T3: NULL saldo_vencido is mapped to 'no_informado', never 0.00."""
    core = InvestmentOfficeSqlCore()
    creditos = await core.obtener_creditos(async_adapter, id_cliente=1)
    assert len(creditos) == 1
    cr = creditos[0]
    assert Decimal(cr["saldo_insoluto_actual"]) == Decimal("1850000.0")
    assert cr["saldo_vencido"] == "no_informado"
    assert cr["fecha_vencimiento"] == "no_informado"
    assert cr["estatus_pago"] == "AL CORRIENTE"


@pytest.mark.asyncio
async def test_h08_obtener_movimientos(async_adapter):
    core = InvestmentOfficeSqlCore()
    res = await core.obtener_movimientos(
        async_adapter, id_cliente=1, desde=date(2023, 1, 1), hasta=date(2023, 12, 31)
    )
    assert len(res["movimientos"]) == 2
    assert res["cobertura"]["desde"] == "2023-01-07"
    assert res["cobertura"]["hasta"] == "2023-12-25"


@pytest.mark.asyncio
async def test_h09_obtener_asesor(async_adapter):
    core = InvestmentOfficeSqlCore()
    asesores = await core.obtener_asesor(async_adapter, id_cliente=1)
    assert len(asesores) == 1
    asesor = asesores[0]
    assert asesor["nombre_completo"] == "Alberto Hernán Guevara"
    assert asesor["desc_centro_financiero"] == "CF Reforma CDMX"


@pytest.mark.asyncio
async def test_h10_obtener_resumen_inicial(async_adapter):
    core = InvestmentOfficeSqlCore()
    resumen = await core.obtener_resumen_inicial(async_adapter, id_cliente=1)
    assert len(resumen["contratos"]) == 4
    assert resumen["posicion_total"]["valuacion_mixta"] is True
    assert len(resumen["creditos"]) == 1
    assert resumen["asesor"]["nombre_completo"] == "Alberto Hernán Guevara"


@pytest.mark.asyncio
async def test_h11_escalar_a_asesor(async_adapter):
    core = InvestmentOfficeSqlCore()
    esc = await core.escalar_a_asesor(
        async_adapter,
        id_cliente=1,
        motivo="desempeno_o_causa",
        detalle="¿Por qué bajó mi portafolio?",
    )
    assert "Alberto Hernán Guevara" in esc["guion"]
    assert esc["ticket_id"].startswith("TICK-")


@pytest.mark.asyncio
async def test_tool_registry_registration(io_sqlite):
    engine = AsyncSqliteEngine(io_sqlite)
    registry = ToolRegistry()
    register_investment_office_tools(registry, engine)
    assert "listar_contratos" in registry
    assert "obtener_posicion_total" in registry
    assert "obtener_posiciones" in registry
    assert "obtener_saldos_por_producto" in registry
    assert "obtener_vencimientos" in registry
    assert "obtener_polizas" in registry
    assert "obtener_creditos" in registry
    assert "obtener_movimientos" in registry
    assert "obtener_asesor" in registry
    assert "obtener_resumen_inicial" in registry
    assert "escalar_a_asesor" in registry

    # Test calling a tool through registry
    spec = registry.get("listar_contratos")
    assert spec.name == "listar_contratos"
    res = await spec.fn("1")
    assert len(res) == 4
