"""Build ``deps.Repositories`` over a session factory (SQL) or in memory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from actinver_agent.deps import Repositories
from actinver_agent.persistence import memory
from actinver_agent.persistence import repositories as sql
from actinver_agent.persistence.repositories import SessionFactory


def create_repositories(
    sessions: SessionFactory, *, engine: AsyncEngine, service_identity: str = "agent_svc"
) -> Repositories:
    return Repositories(
        threads=sql.SqlThreadRepository(sessions, service_identity=service_identity, engine=engine),
        consents=sql.SqlConsentRepository(sessions, service_identity=service_identity),
        devices=sql.SqlDeviceRepository(sessions, service_identity=service_identity),
        form_specs=sql.SqlFormSpecRepository(sessions, service_identity=service_identity),
        idempotency=sql.SqlIdempotencyRepository(sessions, service_identity=service_identity),
        challenges=sql.SqlChallengeRepository(sessions, service_identity=service_identity),
        avatar_sessions=sql.SqlAvatarSessionRepository(sessions, service_identity=service_identity),
        evidence_index=sql.SqlEvidenceIndexRepository(sessions, service_identity=service_identity),
        access_log=sql.SqlAccessLogRepository(sessions, service_identity=service_identity),
        arco=sql.SqlArcoRepository(sessions, service_identity=service_identity),
        rulesets=sql.SqlRulesetRepository(sessions, service_identity=service_identity),
        audio_segments=sql.SqlAudioSegmentRepository(sessions, service_identity=service_identity),
    )


def create_memory_repositories() -> Repositories:
    mem = memory.MemoryRepositories()
    return Repositories(
        threads=mem.threads,
        consents=mem.consents,
        devices=mem.devices,
        form_specs=mem.form_specs,
        idempotency=mem.idempotency,
        challenges=mem.challenges,
        avatar_sessions=mem.avatar_sessions,
        evidence_index=mem.evidence_index,
        access_log=mem.access_log,
        arco=mem.arco,
        rulesets=mem.rulesets,
        audio_segments=mem.audio_segments,
    )
