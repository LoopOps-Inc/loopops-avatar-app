"""FastAPI application for the agent role (bff-mobile + agent-orchestrator +
avatar-broker + voice-pipeline surface).

OpenAPI 3.1 is generated from the Pydantic models and is the source of truth
for the client contract (docs/04-backend/04). Errors are RFC 9457 problem
details. Guardrail refusals are never HTTP errors.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from actinver_agent.api.routes import (
    auth,
    avatar,
    compliance,
    config,
    consents,
    forms,
    health,
    sessions,
    telemetry,
    threads,
)
from actinver_agent.api.schemas import SseEventCatalogue
from actinver_agent.config import Settings, get_settings
from actinver_agent.deps import Dependencies, set_current
from actinver_agent.errors import (
    ApiError,
    ProblemDetails,
    api_error,
    current_trace_id,
    problem_response,
)
from actinver_agent.observability.setup import configure_logging, configure_tracing
from actinver_agent.secrets import assert_reference_fields

log = structlog.get_logger(__name__)

DepsFactory = Callable[[Settings], Awaitable[Dependencies]]

OPENAPI_TAGS = [
    {"name": "sessions", "description": "App session, capabilities and required disclosures."},
    {"name": "threads", "description": "Chat turns over SSE and thread history."},
    {"name": "forms", "description": "Server-driven transactional forms (ADR-0009)."},
    {"name": "auth", "description": "Step-up challenges (ADR-0017)."},
    {"name": "avatar", "description": "LiveAvatar LITE sessions and the audio WebSocket."},
    {
        "name": "consents",
        "description": "Acknowledgements and revocable consents (DCGSI Art. 24/26, LFPDPPP).",
    },
    {"name": "config", "description": "Remote config and kill-switch poll (ADR-0015)."},
    {"name": "telemetry", "description": "Client telemetry ingest."},
    {"name": "compliance", "description": "Compliance console, flags, incident response, ARCO."},
    {"name": "health", "description": "Probes."},
]


async def _default_factory(settings: Settings) -> Dependencies:
    from actinver_agent.wiring import build_dependencies

    return await build_dependencies(settings)


async def assert_suitability_key_unreadable(deps: Dependencies) -> None:
    """The agent role must not be able to read the suitability HMAC key
    (docs/05-security/04 §2). Only meaningful when the engine is a separate service."""
    if deps.settings.services.suitability_url == "inprocess":
        return
    if await deps.secrets.try_resolve(deps.settings.suitability_signing_key_ref) is not None:
        raise RuntimeError(
            "P1 configuration defect: the agent can read the suitability signing key "
            "(SUITABILITY_SIGNING_KEY_REF must not be resolvable by the agent role)"
        )


def create_app(
    deps_factory: DepsFactory | None = None, *, settings: Settings | None = None
) -> FastAPI:
    settings = settings or get_settings()
    factory = deps_factory or _default_factory

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        configure_tracing(settings.service_name, settings.otlp_endpoint)
        assert_reference_fields(settings)
        deps = await factory(settings)
        await assert_suitability_key_unreadable(deps)
        set_current(deps)
        app.state.deps = deps
        log.info(
            "startup.complete", environment=str(settings.environment), role=settings.service_role
        )
        try:
            yield
        finally:
            if deps.broker is not None:
                with contextlib.suppress(Exception):
                    await deps.broker.stop_all(reason="shutdown")
            await deps.aclose()
            set_current(None)
            log.info("shutdown.complete")

    show_docs = settings.environment in ("local", "dev")
    app = FastAPI(
        title="Actinver AI Advisor - Agent API",
        version="1.0.0",
        description=(
            "Mobile/web-facing API of the Actinver AI Advisor (bff-mobile + agent-orchestrator + "
            "avatar-broker). Path-versioned (`/v1/`), RFC 9457 errors with a Spanish `message`, "
            "`Idempotency-Key` on every mutating endpoint, cursor pagination, SSE for chat turns "
            "and a WebSocket for the bidirectional audio path. Auth: `Authorization: DPoP <token>` "
            "plus a `DPoP` proof header (plain `Bearer` accepted in local only)."
        ),
        lifespan=lifespan,
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id", "Retry-After"],
    )

    @app.middleware("http")
    async def trace_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        structlog.contextvars.clear_contextvars()
        response = await call_next(request)
        response.headers["X-Trace-Id"] = current_trace_id()
        return response

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return problem_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg')}"
            for e in exc.errors()[:5]
        )
        return problem_response(request, api_error("VALIDATION_ERROR", detail=detail[:500]))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", error_type=type(exc).__name__)
        return problem_response(request, api_error("INTERNAL_ERROR"))

    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(threads.router)
    app.include_router(forms.router)
    app.include_router(auth.router)
    app.include_router(avatar.router)
    app.include_router(consents.router)
    app.include_router(config.router)
    app.include_router(telemetry.router)
    app.include_router(compliance.router)

    _extend_openapi(app)
    FastAPIInstrumentor.instrument_app(app)
    return app


def _extend_openapi(app: FastAPI) -> None:
    """Register the SSE catalogue, the problem-details schema and the WS protocol."""
    original = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components["ProblemDetails"] = ProblemDetails.model_json_schema()
        sse = SseEventCatalogue.model_json_schema()
        for name, definition in sse.pop("$defs", {}).items():
            components.setdefault(name, definition)
        components["SseEventCatalogue"] = sse
        schema["x-sse-events"] = {
            "endpoint": "POST /v1/threads/{thread_id}/messages",
            "events": ["token", "ui", "form_spec", "citations", "error", "done"],
            "note": "done always fires, including after error",
        }
        schema["x-websocket"] = {
            "path": "/v1/avatar/{avatar_session_id}/audio",
            "auth": "?access_token=<jwt> or first message {type:'auth',token}",
            "client_to_server": [
                "binary audio frame",
                "audio_start",
                "utterance_end",
                "client.barge_in",
                "client.background",
                "client.foreground",
                "dev.transcript (VOICE_PROVIDER=stub only)",
            ],
            "server_to_client": [
                "transcript.partial",
                "transcript.final",
                "agent.thinking",
                "agent.speaking",
                "filler",
                "caption",
                "ui",
                "form_spec",
                "citations",
                "error",
                "turn.complete",
                "session.refreshed",
                "session.expiring",
                "session.closed",
            ],
            "close_codes": {
                "4401": "unauthenticated",
                "4403": "not the owner",
                "4404": "unknown session",
            },
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
