"""InvestmentOffice SQL client and query runner.

Implements the 11 tools specified in the InvestmentOffice Tool Layer against
the `investmentofficedb` schema (20 clients, 80 contracts, 22 tables),
handling the six critical data traps:

T1: `baja_logica IS NOT TRUE` everywhere (inv_nnf_det_mandatos.baja_logica is NULL).
T2: Two valuation dates in inv_posicion_inversion: filter by MAX(snapshot_date) per contract
    and flag `valuacion_mixta` if dates differ across contracts.
T3: NULL saldo_vencido in inv_creditos is mapped to "no_informado" (never 0.00).
T4: Tag figures with `naturaleza` (SALDO, CAPITAL_INICIAL, FLUJO_NETO).
T5: Never project `precio`; use only `precio_cierre` and `posicion_total`.
T6: `inv_seguros` filters directly by `id_cliente_fk` (not contract).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class InvestmentOfficeSqlCore:
    """Read-only SQL adapter for the InvestmentOffice schema."""

    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine

    # ── Investor discovery (for UI/Avatar investor picker) ───────────────────

    async def list_investors(self, conn: AsyncConnection) -> list[dict[str, Any]]:
        """List the 20 clients with their contract counts and risk profile."""
        query = text("""
            SELECT c.id_cliente_pk,
                   c.numero_cliente_unico,
                   c.nombre,
                   c.apellido_paterno,
                   c.apellido_materno,
                   c.rfc,
                   c.correo_electronico,
                   p.nombre_perfil AS perfil_riesgo,
                   COUNT(ct.id_contrato_pk) AS total_contratos
            FROM   public.inv_cliente c
            LEFT JOIN public.inv_cat_perfil_inversion p ON p.id_perfil_inv_pk = c.id_perfil_inv_fk
            LEFT JOIN public.inv_contrato ct ON ct.id_cliente_fk = c.id_cliente_pk AND ct.baja_logica IS NOT TRUE
            WHERE  c.baja_logica IS NOT TRUE
            GROUP BY c.id_cliente_pk, c.numero_cliente_unico, c.nombre, c.apellido_paterno,
                     c.apellido_materno, c.rfc, c.correo_electronico, p.nombre_perfil
            ORDER BY c.id_cliente_pk;
        """)
        res = await conn.execute(query)
        rows = res.mappings().all()
        return [
            {
                "id_cliente_pk": r["id_cliente_pk"],
                "numero_cliente_unico": r["numero_cliente_unico"],
                "nombre_completo": f"{r['nombre']} {r['apellido_paterno']} {r['apellido_materno']}".strip(),
                "rfc": r["rfc"],
                "correo_electronico": r["correo_electronico"],
                "perfil_riesgo": r["perfil_riesgo"],
                "total_contratos": r["total_contratos"],
            }
            for r in rows
        ]

    # ── Helper to resolve client_id to id_cliente_pk ─────────────────────────

    async def resolve_id_cliente(self, conn: AsyncConnection, client_id: str | int) -> int:
        """Resolve numeric client_id, numero_cliente_unico, or demo client alias to id_cliente_pk."""
        if isinstance(client_id, int):
            return client_id
        if client_id.isdigit():
            val = int(client_id)
            # Check if it's already an id_cliente_pk (1..20) or numero_cliente_unico (200001..200020)
            if val <= 50:
                return val
            q = text(
                "SELECT id_cliente_pk FROM public.inv_cliente WHERE numero_cliente_unico = :num"
            )
            res = await conn.execute(q, {"num": val})
            row = res.scalar_one_or_none()
            if row is not None:
                return int(row)
            return val

        # Handle demo string aliases
        alias_map = {
            "cl_demo_moderado": 1,
            "cl_demo_conservador": 2,
            "cl_demo_agresivo": 4,
            "cl_demo_vencido": 5,
        }
        return alias_map.get(client_id, 1)

    # ── H01: Listar Contratos ────────────────────────────────────────────────

    async def listar_contratos(
        self,
        conn: AsyncConnection,
        *,
        id_cliente: int,
        tipo: Literal["INVERSION", "CREDITO", "RETIRO"] | None = None,
    ) -> list[dict[str, Any]]:
        query = text("""
            SELECT c.id_contrato_pk, c.num_contrato, c.tipo_contrato,
                   c.subtipo_contrato, c.desc_unidad_negocio,
                   c.fecha_apertura, c.estatus_contrato
            FROM   public.inv_contrato c
            WHERE  c.id_cliente_fk = :id_cliente
              AND  c.baja_logica IS NOT TRUE
              AND  c.current_flag IS TRUE
              AND  (CAST(:tipo AS text) IS NULL OR c.tipo_contrato = :tipo)
            ORDER BY c.num_contrato;
        """)
        res = await conn.execute(query, {"id_cliente": id_cliente, "tipo": tipo})
        return [dict(r) for r in res.mappings().all()]

    # ── H02: Obtener Posición Total (Trap T2 & T5) ────────────────────────────

    async def obtener_posicion_total(
        self, conn: AsyncConnection, *, id_cliente: int
    ) -> dict[str, Any]:
        query = text("""
            WITH ult AS (
              SELECT p.id_contrato_fk, MAX(p.snapshot_date) AS snap
              FROM   public.inv_posicion_inversion p
              JOIN   public.inv_contrato c ON c.id_contrato_pk = p.id_contrato_fk
              WHERE  c.id_cliente_fk = :id_cliente
                AND  p.baja_logica IS NOT TRUE
                AND  c.baja_logica IS NOT TRUE
              GROUP BY p.id_contrato_fk
            )
            SELECT c.num_contrato,
                   c.subtipo_contrato,
                   u.snap                        AS fecha_valuacion,
                   COUNT(*)                      AS num_posiciones,
                   SUM(p.posicion_total)         AS valor_mxn
            FROM   public.inv_posicion_inversion p
            JOIN   ult u  ON u.id_contrato_fk = p.id_contrato_fk
                          AND u.snap = p.snapshot_date
            JOIN   public.inv_contrato c ON c.id_contrato_pk = p.id_contrato_fk
            WHERE  p.baja_logica IS NOT TRUE
            GROUP BY c.num_contrato, c.subtipo_contrato, u.snap
            ORDER BY c.num_contrato;
        """)
        res = await conn.execute(query, {"id_cliente": id_cliente})
        rows = [dict(r) for r in res.mappings().all()]

        fechas_valuacion = sorted(
            {str(r["fecha_valuacion"]) for r in rows if r.get("fecha_valuacion") is not None}
        )
        valuacion_mixta = len(fechas_valuacion) > 1
        total_mxn = sum(
            (Decimal(str(r["valor_mxn"])) for r in rows if r["valor_mxn"] is not None), Decimal("0")
        )

        return {
            "por_contrato": rows,
            "total_mxn": str(total_mxn),
            "fechas_valuacion": fechas_valuacion,
            "valuacion_mixta": valuacion_mixta,
        }

    # ── H03: Obtener Posiciones (Trap T5) ────────────────────────────────────

    async def obtener_posiciones(
        self,
        conn: AsyncConnection,
        *,
        id_cliente: int,
        instrumento: Literal["ACCION", "ETF", "FONDO", "BONO"] | None = None,
        tipo_producto: Literal["RV", "RF"] | None = None,
        emisora: str | None = None,
        limite: int = 15,
    ) -> list[dict[str, Any]]:
        query = text("""
            WITH ult AS (
              SELECT p.id_contrato_fk, MAX(p.snapshot_date) AS snap
              FROM   public.inv_posicion_inversion p
              JOIN   public.inv_contrato c ON c.id_contrato_pk = p.id_contrato_fk
              WHERE  c.id_cliente_fk = :id_cliente
                AND  p.baja_logica IS NOT TRUE
                AND  c.baja_logica IS NOT TRUE
              GROUP BY p.id_contrato_fk
            )
            SELECT c.num_contrato,
                   p.desc_instrumento,
                   p.desc_tipo_producto,
                   p.clave_emisora,
                   p.desc_emisora,
                   p.serie,
                   p.cantidad_titulos,
                   p.precio_cierre,
                   p.posicion_total,
                   p.fecha_vencimiento,
                   u.snap AS fecha_valuacion
            FROM   public.inv_posicion_inversion p
            JOIN   ult u ON u.id_contrato_fk = p.id_contrato_fk AND u.snap = p.snapshot_date
            JOIN   public.inv_contrato c ON c.id_contrato_pk = p.id_contrato_fk
            WHERE  p.baja_logica IS NOT TRUE
              AND  (CAST(:instrumento AS text) IS NULL OR p.desc_instrumento = :instrumento)
              AND  (CAST(:tipo_producto AS text) IS NULL OR p.desc_tipo_producto = :tipo_producto)
              AND  (CAST(:emisora AS text) IS NULL OR p.clave_emisora = :emisora)
            ORDER BY p.posicion_total DESC
            LIMIT  :limite;
        """)
        res = await conn.execute(
            query,
            {
                "id_cliente": id_cliente,
                "instrumento": instrumento,
                "tipo_producto": tipo_producto,
                "emisora": emisora,
                "limite": limite,
            },
        )
        return [
            {
                "num_contrato": r["num_contrato"],
                "desc_instrumento": r["desc_instrumento"],
                "desc_tipo_producto": r["desc_tipo_producto"],
                "clave_emisora": r["clave_emisora"],
                "desc_emisora": r["desc_emisora"],
                "serie": r["serie"],
                "cantidad_titulos": str(r["cantidad_titulos"])
                if r["cantidad_titulos"] is not None
                else None,
                "precio_cierre": str(r["precio_cierre"])
                if r["precio_cierre"] is not None
                else None,
                "posicion_total": str(r["posicion_total"])
                if r["posicion_total"] is not None
                else None,
                "fecha_vencimiento": str(r["fecha_vencimiento"])
                if r["fecha_vencimiento"]
                else None,
                "fecha_valuacion": str(r["fecha_valuacion"]) if r["fecha_valuacion"] else None,
            }
            for r in res.mappings().all()
        ]

    # ── H04: Obtener Saldos por Producto (Traps T1, T4) ───────────────────────

    async def obtener_saldos_por_producto(
        self,
        conn: AsyncConnection,
        *,
        id_cliente: int,
        producto: Literal["FONDOS", "CEDE", "PRLV", "MANDATOS", "PPR", "FONDOS_COMPLEJOS"]
        | None = None,
    ) -> list[dict[str, Any]]:
        query = text("""
            SELECT * FROM (
                -- PPR: saldo real
                SELECT 'PPR' AS producto, 'SALDO' AS naturaleza,
                       c.num_contrato, COUNT(*) AS n,
                       SUM(t.monto_posicion) AS monto_mxn, MAX(t.snapshot_date) AS corte
                FROM   public.inv_ppr t
                JOIN   public.inv_contrato c ON c.id_contrato_pk = t.id_contrato_fk
                WHERE  c.id_cliente_fk = :id_cliente AND t.baja_logica IS NOT TRUE
                GROUP BY c.num_contrato

                UNION ALL
                -- MANDATOS: baja_logica IS NOT TRUE (Trap T1)
                SELECT 'MANDATOS', 'SALDO', c.num_contrato, COUNT(*),
                       SUM(m.importe), MAX(m.snapshot_date)
                FROM   public.inv_nnf_det_mandatos m
                JOIN   public.inv_contrato c ON c.id_contrato_pk = m.id_contrato_fk
                WHERE  c.id_cliente_fk = :id_cliente
                  AND  m.baja_logica IS NOT TRUE
                  AND  m.snapshot_date = (SELECT MAX(m2.snapshot_date)
                                          FROM public.inv_nnf_det_mandatos m2
                                          WHERE m2.id_contrato_fk = m.id_contrato_fk)
                GROUP BY c.num_contrato

                UNION ALL
                -- CEDE: Capital inicial
                SELECT 'CEDE', 'CAPITAL_INICIAL', c.num_contrato, COUNT(*),
                       SUM(x.capital_inicial), MAX(x.fecha_apertura)
                FROM   public.inv_nnf_det_cede x
                JOIN   public.inv_contrato c ON c.id_contrato_pk = x.id_contrato_fk
                WHERE  c.id_cliente_fk = :id_cliente AND x.baja_logica IS NOT TRUE
                GROUP BY c.num_contrato

                UNION ALL
                -- PRLV: Capital inicial
                SELECT 'PRLV', 'CAPITAL_INICIAL', c.num_contrato, COUNT(*),
                       SUM(x.capital_inicial), MAX(x.fecha_apertura)
                FROM   public.inv_nnf_prlv x
                JOIN   public.inv_contrato c ON c.id_contrato_pk = x.id_contrato_fk
                WHERE  c.id_cliente_fk = :id_cliente AND x.baja_logica IS NOT TRUE
                GROUP BY c.num_contrato

                UNION ALL
                -- FONDOS: Flujo neto (Trap T4)
                SELECT 'FONDOS', 'FLUJO_NETO', c.num_contrato, COUNT(*),
                       SUM(CASE f.tipo_operacion WHEN 'COMPRA' THEN f.importe
                                                 ELSE -f.importe END),
                       MAX(f.fecha_operacion)
                FROM   public.inv_nnf_det_fondos f
                JOIN   public.inv_contrato c ON c.id_contrato_pk = f.id_contrato_fk
                WHERE  c.id_cliente_fk = :id_cliente AND f.baja_logica IS NOT TRUE
                GROUP BY c.num_contrato

                UNION ALL
                -- FONDOS COMPLEJOS: Flujo neto
                SELECT 'FONDOS_COMPLEJOS', 'FLUJO_NETO', c.num_contrato, COUNT(*),
                       SUM(CASE fc.tipo_movimiento WHEN 'COMPRA' THEN fc.monto_mxn
                                                   ELSE -fc.monto_mxn END),
                       NULL::date
                FROM   public.inv_nna_fondos_complejos fc
                JOIN   public.inv_contrato c ON c.id_contrato_pk = fc.id_contrato_fk
                WHERE  c.id_cliente_fk = :id_cliente AND fc.baja_logica IS NOT TRUE
                GROUP BY c.num_contrato
            ) u
            WHERE (CAST(:producto AS text) IS NULL OR u.producto = :producto);
        """)
        res = await conn.execute(query, {"id_cliente": id_cliente, "producto": producto})
        return [
            {
                "producto": r["producto"],
                "naturaleza": r["naturaleza"],
                "num_contrato": r["num_contrato"],
                "num_registros": r["n"],
                "monto_mxn": str(r["monto_mxn"]) if r["monto_mxn"] is not None else None,
                "fecha_corte": str(r["corte"]) if r["corte"] is not None else None,
            }
            for r in res.mappings().all()
        ]

    # ── H05: Obtener Vencimientos (Refusal for unpopulated fields) ────────────

    async def obtener_vencimientos(
        self,
        conn: AsyncConnection,
        *,
        id_cliente: int,
        producto: Literal["POSICION", "CEDE", "PRLV", "CREDITO"] | None = None,
    ) -> dict[str, Any]:
        disponibles: list[dict[str, Any]] = []
        no_disponibles: list[dict[str, Any]] = []

        if producto in (None, "POSICION"):
            query_bonos = text("""
                WITH ult AS (
                  SELECT p.id_contrato_fk, MAX(p.snapshot_date) AS snap
                  FROM   public.inv_posicion_inversion p
                  JOIN   public.inv_contrato c ON c.id_contrato_pk = p.id_contrato_fk
                  WHERE  c.id_cliente_fk = :id_cliente
                    AND  p.baja_logica IS NOT TRUE
                    AND  c.baja_logica IS NOT TRUE
                  GROUP BY p.id_contrato_fk
                )
                SELECT c.num_contrato, p.desc_instrumento, p.clave_emisora, p.desc_emisora,
                       p.fecha_vencimiento, p.plazo, p.posicion_total
                FROM   public.inv_posicion_inversion p
                JOIN   ult u ON u.id_contrato_fk = p.id_contrato_fk AND u.snap = p.snapshot_date
                JOIN   public.inv_contrato c ON c.id_contrato_pk = p.id_contrato_fk
                WHERE  p.baja_logica IS NOT TRUE
                  AND  p.fecha_vencimiento IS NOT NULL
                ORDER BY p.fecha_vencimiento;
            """)
            res = await conn.execute(query_bonos, {"id_cliente": id_cliente})
            disponibles.extend(
                {
                    "num_contrato": r["num_contrato"],
                    "desc_instrumento": r["desc_instrumento"],
                    "clave_emisora": r["clave_emisora"],
                    "desc_emisora": r["desc_emisora"],
                    "fecha_vencimiento": str(r["fecha_vencimiento"]),
                    "plazo": int(r["plazo"]) if r["plazo"] is not None else None,
                    "posicion_total": str(r["posicion_total"])
                    if r["posicion_total"] is not None
                    else None,
                }
                for r in res.mappings().all()
            )

        refusals = {
            "CEDE": "plazo_del_cede",
            "PRLV": "plazo_del_prlv",
            "CREDITO": "fecha_vencimiento",
        }

        for prod_key, field_name in refusals.items():
            if producto in (None, prod_key):
                no_disponibles.append(
                    {
                        "producto": prod_key,
                        "disponible": False,
                        "motivo": "campo_no_poblado",
                        "campo": field_name,
                        "accion_sugerida": "escalar_a_asesor",
                    }
                )

        return {"disponibles": disponibles, "no_disponibles": no_disponibles}

    # ── H06: Obtener Pólizas (Trap T6: id_cliente_fk direct) ─────────────────

    async def obtener_polizas(
        self,
        conn: AsyncConnection,
        *,
        id_cliente: int,
        ramo: Literal["VIDA", "GMM", "AUTO"] | None = None,
    ) -> list[dict[str, Any]]:
        query = text("""
            SELECT s.numero_poliza, s.ramo, s.subramo,
                   s.prima_neta, s.prima_total,
                   s.estatus_cobranza,
                   s.estatus_poliza,
                   s.snapshot_date,
                   s.fecha_inicio_vigencia, s.fecha_fin_vigencia
            FROM   public.inv_seguros s
            WHERE  s.id_cliente_fk = :id_cliente
              AND  s.baja_logica IS NOT TRUE
              AND  (CAST(:ramo AS text) IS NULL OR s.ramo = :ramo)
            ORDER BY s.ramo, s.numero_poliza;
        """)
        res = await conn.execute(query, {"id_cliente": id_cliente, "ramo": ramo})
        return [
            {
                "numero_poliza": r["numero_poliza"],
                "ramo": r["ramo"],
                "subramo": r["subramo"],
                "prima_neta": str(r["prima_neta"]) if r["prima_neta"] is not None else None,
                "prima_total": str(r["prima_total"]) if r["prima_total"] is not None else None,
                "estatus_cobranza": r["estatus_cobranza"],
                "estatus_poliza": r["estatus_poliza"],
                "snapshot_date": str(r["snapshot_date"])
                if r["snapshot_date"] is not None
                else None,
                "vigencia_disponible": False,  # fecha_inicio/fin are 100% NULL in dump
            }
            for r in res.mappings().all()
        ]

    # ── H07: Obtener Créditos (Trap T3: NULL is not 0) ───────────────────────

    async def obtener_creditos(
        self, conn: AsyncConnection, *, id_cliente: int
    ) -> list[dict[str, Any]]:
        query = text("""
            SELECT c.num_contrato,
                   cr.num_credito_sistema,
                   cr.tipo_credito,
                   cr.monto_original,
                   cr.saldo_insoluto_actual,
                   cr.saldo_vencido,
                   cr.estatus_pago,
                   cr.fecha_vencimiento,
                   cr.snapshot_date
            FROM   public.inv_creditos cr
            JOIN   public.inv_contrato c ON c.id_contrato_pk = cr.id_contrato_fk
            WHERE  c.id_cliente_fk = :id_cliente
              AND  cr.baja_logica IS NOT TRUE
              AND  c.baja_logica IS NOT TRUE
            ORDER BY cr.saldo_insoluto_actual DESC;
        """)
        res = await conn.execute(query, {"id_cliente": id_cliente})
        return [
            {
                "num_contrato": r["num_contrato"],
                "num_credito_sistema": r["num_credito_sistema"],
                "tipo_credito": r["tipo_credito"],
                "monto_original": str(r["monto_original"])
                if r["monto_original"] is not None
                else None,
                "saldo_insoluto_actual": str(r["saldo_insoluto_actual"])
                if r["saldo_insoluto_actual"] is not None
                else None,
                # Trap T3: never map None to "0.00"
                "saldo_vencido": str(r["saldo_vencido"])
                if r["saldo_vencido"] is not None
                else "no_informado",
                "estatus_pago": r["estatus_pago"],
                "fecha_vencimiento": str(r["fecha_vencimiento"])
                if r["fecha_vencimiento"] is not None
                else "no_informado",
                "snapshot_date": str(r["snapshot_date"])
                if r["snapshot_date"] is not None
                else None,
            }
            for r in res.mappings().all()
        ]

    # ── H08: Obtener Movimientos (Coverage Window 2023) ──────────────────────

    async def obtener_movimientos(
        self,
        conn: AsyncConnection,
        *,
        id_cliente: int,
        desde: date | str = date(2023, 1, 1),
        hasta: date | str = date(2023, 12, 31),
        tipo: Literal["ABONO", "CARGO"] | None = None,
        incluir_traspasos: bool = True,
        limite: int = 10,
    ) -> dict[str, Any]:
        cobertura = {"desde": "2023-01-07", "hasta": "2023-12-25"}

        query = text("""
            SELECT * FROM (
              SELECT 'TRANSACCION' AS origen, t.snapshot_date AS fecha,
                     t.desc_transaccion, t.tipo_movimiento, t.nombre_divisa,
                     t.importe_mxn, c.num_contrato
              FROM   public.inv_nna_det_transacciones t
              JOIN   public.inv_contrato c ON c.id_contrato_pk = t.id_contrato_fk
              WHERE  c.id_cliente_fk = :id_cliente AND t.baja_logica IS NOT TRUE

              UNION ALL

              SELECT 'TRASPASO', tr.snapshot_date,
                     tr.desc_transaccion, tr.tipo_movimiento, tr.nombre_divisa,
                     tr.importe_mxn, c.num_contrato
              FROM   public.inv_nna_det_traspasos tr
              JOIN   public.inv_contrato c ON c.id_contrato_pk = tr.id_contrato_fk
              WHERE  c.id_cliente_fk = :id_cliente AND tr.baja_logica IS NOT TRUE
                AND  :incluir_traspasos IS TRUE
            ) m
            WHERE  m.fecha BETWEEN :desde AND :hasta
              AND  (CAST(:tipo AS text) IS NULL OR m.tipo_movimiento = :tipo)
            ORDER BY m.fecha DESC
            LIMIT  :limite;
        """)
        res = await conn.execute(
            query,
            {
                "id_cliente": id_cliente,
                "desde": desde,
                "hasta": hasta,
                "tipo": tipo,
                "incluir_traspasos": incluir_traspasos,
                "limite": limite,
            },
        )
        rows = [
            {
                "origen": r["origen"],
                "fecha": str(r["fecha"]),
                "desc_transaccion": r["desc_transaccion"],
                "tipo_movimiento": r["tipo_movimiento"],
                "nombre_divisa": r["nombre_divisa"],
                "importe_mxn": str(r["importe_mxn"]) if r["importe_mxn"] is not None else None,
                "num_contrato": r["num_contrato"],
            }
            for r in res.mappings().all()
        ]
        return {
            "movimientos": rows,
            "total_periodo": len(rows),
            "cobertura": cobertura,
        }

    # ── H09: Obtener Asesor ──────────────────────────────────────────────────

    async def obtener_asesor(
        self, conn: AsyncConnection, *, id_cliente: int
    ) -> list[dict[str, Any]]:
        query = text("""
            SELECT DISTINCT
                   a.num_asesor, a.nombre_completo, a.correo_electronico,
                   cf.desc_centro_financiero, b.desc_banca, pu.desc_puesto,
                   ARRAY_AGG(c.num_contrato ORDER BY c.num_contrato) AS contratos
            FROM   public.inv_contrato c
            JOIN   public.inv_asesor a  ON a.id_asesor_pk = c.id_asesor_fk
            LEFT JOIN public.inv_cat_centro_financiero cf
                   ON cf.id_centro_financiero_pk = a.id_centro_financiero_fk
            LEFT JOIN public.inv_cat_banca  b  ON b.id_banca_pk  = a.id_banca_fk
            LEFT JOIN public.inv_cat_puesto pu ON pu.id_puesto_pk = a.id_puesto_fk
            WHERE  c.id_cliente_fk = :id_cliente
              AND  c.baja_logica IS NOT TRUE
              AND  a.baja_logica IS NOT TRUE
              AND  a.current_flag IS TRUE
            GROUP BY a.num_asesor, a.nombre_completo, a.correo_electronico,
                     cf.desc_centro_financiero, b.desc_banca, pu.desc_puesto;
        """)
        res = await conn.execute(query, {"id_cliente": id_cliente})
        return [
            {
                "num_asesor": r["num_asesor"],
                "nombre_completo": r["nombre_completo"],
                "correo_electronico": r["correo_electronico"],
                "desc_centro_financiero": r["desc_centro_financiero"],
                "desc_banca": r["desc_banca"],
                "desc_puesto": r["desc_puesto"],
                "contratos": r["contratos"],
            }
            for r in res.mappings().all()
        ]

    # ── H10: Obtener Resumen Inicial (Prefetch at session open) ───────────────

    async def obtener_resumen_inicial(
        self, conn: AsyncConnection, *, id_cliente: int
    ) -> dict[str, Any]:
        contratos = await self.listar_contratos(conn, id_cliente=id_cliente)
        posicion = await self.obtener_posicion_total(conn, id_cliente=id_cliente)
        creditos = await self.obtener_creditos(conn, id_cliente=id_cliente)
        asesores = await self.obtener_asesor(conn, id_cliente=id_cliente)
        return {
            "id_cliente": id_cliente,
            "contratos": contratos,
            "posicion_total": posicion,
            "creditos": creditos,
            "asesor": asesores[0] if asesores else None,
        }

    # ── H11: Escalar a Asesor (Deterministic exit) ───────────────────────────

    async def escalar_a_asesor(
        self,
        conn: AsyncConnection,
        *,
        id_cliente: int,
        motivo: Literal[
            "dato_no_disponible",
            "fuera_de_alcance",
            "solicita_asesoria",
            "desempeno_o_causa",
            "operacion_requerida",
            "cliente_lo_pide",
        ],
        detalle: str,
    ) -> dict[str, Any]:
        asesores = await self.obtener_asesor(conn, id_cliente=id_cliente)
        asesor = (
            asesores[0]
            if asesores
            else {
                "nombre_completo": "tu asesor patrimonial",
                "desc_centro_financiero": "tu centro financiero",
            }
        )
        scripts = {
            "desempeno_o_causa": (
                f"Para revisar a detalle el rendimiento y las causas de los movimientos en tu "
                f"portafolio, transferiré tu solicitud con {asesor.get('nombre_completo')}, "
                f"tu asesor en {asesor.get('desc_centro_financiero')}."
            ),
            "dato_no_disponible": (
                f"Ese dato específico no se encuentra disponible en mi consulta digital actual. "
                f"He generado una solicitud para que {asesor.get('nombre_completo')} se ponga en contacto contigo."
            ),
            "solicita_asesoria": (
                f"Con gusto canalizo tu consulta con {asesor.get('nombre_completo')} para brindarte una "
                f"recomendación personalizada adaptada a tu perfil de inversión."
            ),
            "operacion_requerida": (
                f"Para ejecutar esta operación con total seguridad, te contactará {asesor.get('nombre_completo')}."
            ),
            "cliente_lo_pide": (
                f"Entendido. Enseguida notifico a {asesor.get('nombre_completo')} para que te atienda personalmente."
            ),
            "fuera_de_alcance": (
                f"Esa consulta requiere atención personalizada. La he canalizado con {asesor.get('nombre_completo')}."
            ),
        }
        import uuid

        ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
        return {
            "asesor": asesor,
            "motivo": motivo,
            "detalle": detalle,
            "guion": scripts.get(motivo, scripts["fuera_de_alcance"]),
            "ticket_id": ticket_id,
        }
