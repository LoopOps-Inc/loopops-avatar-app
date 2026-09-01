"""Liveness, readiness and a dependency-aware health surface.

Readiness deliberately fails when ``suitability``, ``guardrail`` or ``audit``
are unavailable: they are fail-closed dependencies, so a pod that cannot reach
them must not receive traffic (docs/04-backend/01 §2, §7).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from actinver_agent.api.schemas import HealthResponse, ReadyResponse
from actinver_agent.auth.dependencies import get_deps
from actinver_agent.deps import Dependencies

router = APIRouter(tags=["health"])

CRITICAL = ("database", "redis", "suitability", "guardrail", "audit")


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 while the process is alive. Carries no dependency state.",
)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/readyz",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description=(
        "Probes every dependency. Returns 503 when a fail-closed dependency "
        "(database, redis, suitability, guardrail, audit) is unreachable."
    ),
    responses={503: {"model": ReadyResponse, "description": "A fail-closed dependency is down"}},
)
async def readiness(response: Response, deps: Dependencies = Depends(get_deps)) -> ReadyResponse:
    checks = await deps.health()
    ready = all(checks.get(name, False) for name in CRITICAL)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(ready=ready, checks=checks)
