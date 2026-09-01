"""suitability-service: deterministic razonabilidad verdicts, signed with the
key only this service holds (docs/05-security/04 §2). Owned by Compliance."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from actinver_agent.config import Settings
from actinver_agent.graph.state import InvestorProfile, ProductProfile, SuitabilityReport
from actinver_agent.secrets import SecretResolver
from actinver_agent.suitability.engine import SuitabilityEngine
from actinver_agent.suitability.rules import RULESETS, EvaluationContext, ruleset_as_json


class ContextIn(BaseModel):
    today: datetime | date
    amount: str
    portfolio_total: str
    current_weight_by_product: dict[str, float] = Field(default_factory=dict)
    current_weight_by_asset_class: dict[str, float] = Field(default_factory=dict)
    liquid_pct: float = 0.0
    diversification_limits: dict[str, float] = Field(default_factory=dict)

    def to_context(self) -> EvaluationContext:
        today = self.today.date() if isinstance(self.today, datetime) else self.today
        return EvaluationContext(
            today=today,
            amount=Decimal(self.amount),
            portfolio_total=Decimal(self.portfolio_total),
            current_weight_by_product=self.current_weight_by_product,
            current_weight_by_asset_class=self.current_weight_by_asset_class,
            liquid_pct=self.liquid_pct,
            diversification_limits=self.diversification_limits,
        )


class EvaluateRequest(BaseModel):
    client_id: str
    profile: InvestorProfile
    products: list[ProductProfile] = Field(max_length=20)
    context: ContextIn


class VerifyResponse(BaseModel):
    valid: bool


def create_app(engine: SuitabilityEngine) -> FastAPI:
    app = FastAPI(title="Actinver AI Advisor - suitability-service", version="0.1.0")

    @app.post("/v1/suitability/evaluate", response_model=SuitabilityReport)
    async def evaluate(body: EvaluateRequest) -> SuitabilityReport:
        return engine.evaluate(body.profile, body.products, body.context.to_context())

    @app.post("/v1/suitability/verify", response_model=VerifyResponse)
    async def verify(report: SuitabilityReport) -> VerifyResponse:
        if report.ruleset_version not in RULESETS:
            raise HTTPException(status_code=422, detail="unknown ruleset version")
        return VerifyResponse(valid=engine.verify(report))

    @app.get("/v1/suitability/rulesets")
    async def rulesets() -> dict[str, Any]:
        return {"versions": sorted(RULESETS), "active": engine.ruleset_version}

    @app.get("/v1/suitability/rulesets/{version}")
    async def ruleset(version: int) -> dict[str, Any]:
        if version not in RULESETS:
            raise HTTPException(status_code=404, detail="unknown ruleset version")
        return ruleset_as_json(version)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, Any]:
        return {"ready": True, "checks": {"ruleset": engine.ruleset_version in RULESETS}}

    return app


async def build_engine(settings: Settings, resolver: SecretResolver) -> SuitabilityEngine:
    key = await resolver.resolve_bytes(settings.suitability_signing_key_ref)
    return SuitabilityEngine(settings.suitability_ruleset_version, key)


def build_service(settings: Settings, resolver: SecretResolver) -> FastAPI:
    """App factory that resolves the signing key at startup (never from env)."""
    holder: dict[str, SuitabilityEngine] = {}

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        holder["engine"] = await build_engine(settings, resolver)
        yield

    outer = FastAPI(
        title="Actinver AI Advisor - suitability-service", version="0.1.0", lifespan=lifespan
    )

    class _Proxy(SuitabilityEngine):
        def __init__(self) -> None:
            pass

        def __getattribute__(self, name: str) -> Any:
            if name in {"_target"}:
                return holder.get("engine")
            engine = holder.get("engine")
            if engine is None:
                raise HTTPException(status_code=503, detail="signing key not resolved")
            return getattr(engine, name)

    inner = create_app(_Proxy())
    outer.mount("", inner)
    return outer


def app() -> FastAPI:
    """uvicorn factory (``serve --role suitability``): resolves the verdict key at startup."""
    from actinver_agent.config import get_settings
    from actinver_agent.persistence.wiring import build_resolver

    settings = get_settings()
    return build_service(settings, build_resolver(settings))
