"""transaction-service: idempotent order placement against the OMS, with
independent re-validation and server-verified step-up (ADR-0010, ADR-0017).

Must not share a process with the agent - the agent is untrusted input to it.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from actinver_agent.config import Settings
from actinver_agent.errors import ApiError, api_error, problem_response
from actinver_agent.graph.state import FormSpec
from actinver_agent.secrets import SecretResolver
from actinver_agent.transactions import errors as txerr
from actinver_agent.transactions.executor import TransactionExecutor


class ChallengeRequest(BaseModel):
    client_id: str
    form_id: str
    amount_hash: str


class ChallengeResponse(BaseModel):
    challenge_id: str
    challenge: str
    expires_at: datetime


class OrderRequest(BaseModel):
    client_id: str
    form_spec: FormSpec
    values: dict[str, Any]
    acknowledgements: list[str] = Field(default_factory=list)
    step_up_assertion: str
    challenge_id: str
    suitability_verdict_id: str | None = None
    jkt: str | None = None
    device_id: str | None = None


class OrderResponse(BaseModel):
    order_id: str
    status: str
    settlement_date: str
    evidence_id: str | None
    idempotent_replay: bool = False


def create_app(executor: TransactionExecutor) -> FastAPI:
    app = FastAPI(title="Actinver AI Advisor - transaction-service", version="0.1.0")

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return problem_response(request, exc)

    @app.exception_handler(txerr.TransactionError)
    async def _tx_error(request: Request, exc: txerr.TransactionError) -> JSONResponse:
        return problem_response(request, api_error(exc.api_code, detail=exc.detail))

    @app.post("/v1/step-up/challenge", response_model=ChallengeResponse)
    async def challenge(body: ChallengeRequest) -> ChallengeResponse:
        issued = await executor.issue_challenge(
            client_id=body.client_id, form_id=body.form_id, amount_hash=body.amount_hash
        )
        return ChallengeResponse(
            challenge_id=issued.challenge_id,
            challenge=issued.challenge,
            expires_at=issued.expires_at,
        )

    @app.post("/v1/orders", response_model=OrderResponse)
    async def place_order(
        body: OrderRequest, idempotency_key: str | None = Header(default=None)
    ) -> OrderResponse:
        if not idempotency_key:
            raise api_error("IDEMPOTENCY_KEY_REQUIRED")
        receipt = await executor.execute(
            client_id=body.client_id,
            form_spec=body.form_spec,
            values=body.values,
            acknowledgements=body.acknowledgements,
            step_up_assertion=body.step_up_assertion,
            challenge_id=body.challenge_id,
            idempotency_key=idempotency_key,
            suitability_verdict_id=body.suitability_verdict_id,
            jkt=body.jkt,
            device_id=body.device_id,
        )
        return OrderResponse(
            order_id=receipt.order_id,
            status=receipt.status,
            settlement_date=receipt.settlement_date,
            evidence_id=receipt.evidence_id,
            idempotent_replay=receipt.idempotent_replay,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, Any]:
        return {"ready": True, "checks": {"executor": True}}

    return app


def build_service(settings: Settings, resolver: SecretResolver) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from actinver_agent.persistence.wiring import build_transaction_backends

        backends = await build_transaction_backends(settings, resolver)
        executor = TransactionExecutor(
            core=backends.core,
            oms=backends.oms,
            form_specs=backends.repos.form_specs,
            idempotency=backends.repos.idempotency,
            challenges=backends.repos.challenges,
            devices=backends.repos.devices,
            audit=backends.audit,
            form_key=backends.form_key,
            form_key_version=1,
            challenge_ttl_s=settings.limits.step_up_challenge_ttl_s,
            idempotency_ttl_s=settings.limits.idempotency_ttl_s,
        )
        app.mount("", create_app(executor))
        yield
        await backends.aclose()

    return FastAPI(
        title="Actinver AI Advisor - transaction-service", version="0.1.0", lifespan=lifespan
    )


def app() -> FastAPI:
    """uvicorn factory (``serve --role transaction``)."""
    from actinver_agent.config import get_settings
    from actinver_agent.persistence.wiring import build_resolver

    settings = get_settings()
    return build_service(settings, build_resolver(settings))
