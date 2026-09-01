"""audit-service: the only writer of WORM evidence (docs/04-backend/01 §2).

The write path must survive the agent failing. Reads of evidence are logged to a
separate audit trail (control EV-05) with the actor and a stated reason.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from actinver_agent.audit.sink import EvidenceUnavailable, EvidenceWriter
from actinver_agent.config import Settings
from actinver_agent.ports import AccessLogRepository, ObjectStorePort
from actinver_agent.secrets import SecretResolver


class WriteRequest(BaseModel):
    record: dict[str, Any]
    fail_closed: bool = True


class WriteResponse(BaseModel):
    evidence_id: str
    content_hash: str | None
    spooled: bool


class VerifyResponse(BaseModel):
    thread_id: str
    ok: bool
    records: int
    first_divergent_evidence_id: str | None


def create_app(
    writer: EvidenceWriter,
    *,
    access_log: AccessLogRepository,
    anchor_store: ObjectStorePort | None = None,
) -> FastAPI:
    app = FastAPI(title="Actinver AI Advisor - audit-service", version="0.1.0")

    @app.post("/v1/evidence", response_model=WriteResponse)
    async def write(body: WriteRequest) -> WriteResponse:
        record = body.record
        for required in (
            "evidence_id",
            "thread_id",
            "turn_id",
            "client_id",
            "created_at",
            "retention",
        ):
            if required not in record:
                raise HTTPException(status_code=422, detail=f"record.{required} is required")
        try:
            result = await writer.write(record, fail_closed=body.fail_closed)
        except EvidenceUnavailable as exc:
            raise HTTPException(status_code=503, detail="evidence store unavailable") from exc
        return WriteResponse(
            evidence_id=result.evidence_id, content_hash=result.content_hash, spooled=result.spooled
        )

    @app.post("/v1/evidence/spool/drain")
    async def drain(limit: int = 100) -> dict[str, int]:
        return {"drained": await writer.drain_spool(limit)}

    @app.get("/v1/evidence/verify/{thread_id}", response_model=VerifyResponse)
    async def verify(thread_id: str) -> VerifyResponse:
        ok, count, first = await writer.verify_thread(thread_id)
        return VerifyResponse(
            thread_id=thread_id, ok=ok, records=count, first_divergent_evidence_id=first
        )

    @app.post("/v1/evidence/anchor")
    async def anchor() -> dict[str, str]:
        if anchor_store is None:
            raise HTTPException(status_code=503, detail="anchor store not configured")
        return {"key": await writer.anchor_heads(anchor_store)}

    @app.post("/v1/evidence/legal-hold/{thread_id}")
    async def legal_hold(
        thread_id: str,
        on: bool = True,
        x_actor: str = Header(default="unknown"),
        x_reason: str = Header(default=""),
    ) -> dict[str, Any]:
        if not x_reason:
            raise HTTPException(status_code=400, detail="X-Reason header is required")
        await access_log.log(
            actor=x_actor,
            action="legal_hold",
            scope={"thread_id": thread_id, "on": on},
            reason=x_reason,
        )
        return {"thread_id": thread_id, "records": await writer.set_legal_hold(thread_id, on=on)}

    @app.get("/v1/evidence/{evidence_id}")
    async def read(
        evidence_id: str,
        x_actor: str = Header(default="unknown"),
        x_reason: str = Header(default=""),
    ) -> dict[str, Any]:
        if not x_reason:
            raise HTTPException(status_code=400, detail="X-Reason header is required")
        await access_log.log(
            actor=x_actor,
            action="read_evidence",
            scope={"evidence_id": evidence_id},
            reason=x_reason,
        )
        record = await writer.read(evidence_id)
        if record is None:
            raise HTTPException(status_code=404, detail="not found")
        return record

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, Any]:
        ok = await writer.health()
        if not ok:
            raise HTTPException(
                status_code=503, detail={"ready": False, "checks": {"object_store": False}}
            )
        return {
            "ready": True,
            "checks": {"object_store": True},
            "at": datetime.now(UTC).isoformat(),
        }

    return app


def build_service(settings: Settings, resolver: SecretResolver) -> FastAPI:
    """Wire the writer against S3 + Postgres (or memory doubles) at startup."""
    holder: dict[str, Any] = {}

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from actinver_agent.persistence.wiring import build_audit_backends

        backends = await build_audit_backends(settings, resolver)
        writer = EvidenceWriter(
            store=backends.store,
            chain=backends.chain,
            index=backends.index,
            spool=backends.spool,
            lock_mode=settings.object_store.lock_mode,
            retention_years=settings.object_store.retention_years,
        )
        inner = create_app(
            writer, access_log=backends.access_log, anchor_store=backends.anchor_store
        )
        app.mount("", inner)
        holder["close"] = backends.aclose
        yield
        await backends.aclose()

    return FastAPI(title="Actinver AI Advisor - audit-service", version="0.1.0", lifespan=lifespan)


def app() -> FastAPI:
    """uvicorn factory (``serve --role audit``)."""
    from actinver_agent.config import get_settings
    from actinver_agent.persistence.wiring import build_resolver

    settings = get_settings()
    return build_service(settings, build_resolver(settings))
