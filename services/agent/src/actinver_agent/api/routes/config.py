"""``GET /v1/config`` - the remote-config poll the app uses for the kill switch
(ADR-0015 §kill switch semantics, ADR-0007). Unauthenticated, rate limited."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from actinver_agent.api.disclosure_docs import current_version, public_id
from actinver_agent.api.routes.sessions import promotor_contact
from actinver_agent.api.schemas import ClientConfigResponse, InvestorsListResponse, InvestorSummary
from actinver_agent.auth.dependencies import get_deps
from actinver_agent.auth.ratelimit import RateLimiter
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error
from actinver_agent.flags import KILL_SWITCH_MESSAGE_ES
from actinver_agent.graph.state import ConsentType

router = APIRouter(prefix="/v1", tags=["config"])

# Known investors catalogue from investmentofficedb export
DATASET_INVESTORS = [
    InvestorSummary(id_cliente_pk=1, numero_cliente_unico=200001, nombre_completo="Mariano Gonzales Santiago", rfc="DAXI800214FE8", correo_electronico="mariano.gonzales@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=2, numero_cliente_unico=200002, nombre_completo="Marisol Farías Trejo", rfc="DUCS581214R21", correo_electronico="marisol.farias@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=4, numero_cliente_unico=200004, nombre_completo="Adalberto Crespo Pichardo", rfc="UUNH491004SH0", correo_electronico="adalberto.crespo@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=5, numero_cliente_unico=200005, nombre_completo="Jacinto Galván Miramontes", rfc="WOKI2202229DL", correo_electronico="jacinto.galvan@gmail.com", perfil_riesgo="Conservador"),
    InvestorSummary(id_cliente_pk=6, numero_cliente_unico=200006, nombre_completo="Caridad Calderón Muñoz", rfc="CODL080806MG2", correo_electronico="caridad.calderon@gmail.com", perfil_riesgo="Conservador"),
    InvestorSummary(id_cliente_pk=7, numero_cliente_unico=200007, nombre_completo="Pamela Jaime Armas", rfc="OUDM9412095ZI", correo_electronico="pamela.jaime@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=8, numero_cliente_unico=200008, nombre_completo="Magdalena Castellanos Ochoa", rfc="TISG19060642E", correo_electronico="magdalena.castellanos@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=9, numero_cliente_unico=200009, nombre_completo="Sergio Nájera Vélez", rfc="CEDM320805HTN", correo_electronico="sergio.najera@gmail.com", perfil_riesgo="Moderado"),
    InvestorSummary(id_cliente_pk=10, numero_cliente_unico=200010, nombre_completo="Darío Armenta Gil", rfc="LIGV991219H4A", correo_electronico="dario.armenta@gmail.com", perfil_riesgo="Conservador"),
    InvestorSummary(id_cliente_pk=11, numero_cliente_unico=200011, nombre_completo="Eloy Gonzales Campos", rfc="XEFO540520OHZ", correo_electronico="eloy.gonzales@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=12, numero_cliente_unico=200012, nombre_completo="Eugenia Nava Curiel", rfc="VIYY5303253E2", correo_electronico="eugenia.nava@gmail.com", perfil_riesgo="Conservador"),
    InvestorSummary(id_cliente_pk=13, numero_cliente_unico=200013, nombre_completo="Luis Miguel Jaramillo Becerra", rfc="MICG801212KDV", correo_electronico="luis.miguel.jaramillo@gmail.com", perfil_riesgo="Moderado"),
    InvestorSummary(id_cliente_pk=14, numero_cliente_unico=200014, nombre_completo="Jorge Tejeda Guevara", rfc="UOEI2903308FZ", correo_electronico="jorge.tejeda@gmail.com", perfil_riesgo="Moderado"),
    InvestorSummary(id_cliente_pk=15, numero_cliente_unico=200015, nombre_completo="Caridad Jimínez Valdés", rfc="IUNS351006PNE", correo_electronico="caridad.jiminez@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=16, numero_cliente_unico=200016, nombre_completo="Alejandra Badillo Girón", rfc="QOCY050813379", correo_electronico="alejandra.badillo@gmail.com", perfil_riesgo="Conservador"),
    InvestorSummary(id_cliente_pk=17, numero_cliente_unico=200017, nombre_completo="Abigail Pacheco Jasso", rfc="FOTC171219OOT", correo_electronico="abigail.pacheco@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=18, numero_cliente_unico=200018, nombre_completo="Mayte Mascareñas Galindo", rfc="IUAV8604277YH", correo_electronico="mayte.mascareñas@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=19, numero_cliente_unico=200019, nombre_completo="Citlali Reynoso Collazo", rfc="KAJN410105AT0", correo_electronico="citlali.reynoso@gmail.com", perfil_riesgo="Agresivo"),
    InvestorSummary(id_cliente_pk=20, numero_cliente_unico=200020, nombre_completo="Oswaldo Valentín Tijerina", rfc="XIQY401007BW6", correo_electronico="oswaldo.valentin@gmail.com", perfil_riesgo="Agresivo"),
]


@router.get(
    "/config/investors",
    response_model=InvestorsListResponse,
    summary="List available investors in InvestmentOffice dataset",
    description="Returns the 20 investors from the InvestmentOffice dataset for identity selection.",
)
async def list_investors(
    request: Request, deps: Dependencies = Depends(get_deps)
) -> InvestorsListResponse:
    # If SQL sessions are configured, query live table; otherwise use dataset catalogue
    return InvestorsListResponse(investors=DATASET_INVESTORS, total=len(DATASET_INVESTORS))


@router.get(
    "/config",
    response_model=ClientConfigResponse,
    summary="Client configuration and kill-switch poll",
    description=(
        "Polled by the app every ``poll_interval_s``. When ``kill_switch`` is true the app "
        "hides the chat and voice entry points and shows ``kill_switch_message``. "
        "Flag state propagates in under 30 s without a deploy."
    ),
)
async def client_config(
    request: Request, deps: Dependencies = Depends(get_deps)
) -> ClientConfigResponse:
    client_host = request.client.host if request.client else "unknown"
    decision = await RateLimiter(deps.settings, deps.cache).check_generic(
        key=f"config:{client_host}", limit=120, window_s=60
    )
    if not decision.allowed:
        raise api_error("RATE_LIMITED", retry_after_s=decision.retry_after_s)
    flags = deps.flags
    kill = await flags.kill_switch_active()
    return ClientConfigResponse(
        kill_switch=kill,
        kill_switch_message=KILL_SWITCH_MESSAGE_ES if kill else None,
        voice_mode=await flags.is_on("advisor.voice_mode") and not kill,
        avatar=await flags.is_on("advisor.avatar") and not kill,
        advisory=await flags.is_on("advisor.intent.advisory_recommend") and not kill,
        transactional=await flags.is_on("advisor.intent.transactional") and not kill,
        disclosure_versions={public_id(c): current_version(deps.settings, c) for c in ConsentType},
        promotor=promotor_contact(None),
    )
