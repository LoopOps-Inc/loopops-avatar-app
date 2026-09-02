"""SQLAlchemy (async) repositories. Domain code never sees a SQL string or a
driver type (docs/04-backend/02 §4).

Every repository binds the RLS identity per transaction through
``identity_scope``. ``service_identity`` is the SPIFFE-style name of the calling
service; ``client_id`` scopes client rows.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from actinver_agent.graph.state import ConsentRecord, ConsentType, FormSpec
from actinver_agent.persistence import models as m
from actinver_agent.persistence.db import health as db_health
from actinver_agent.persistence.db import identity_scope
from actinver_agent.persistence.thread_id import derive_thread_id
from actinver_agent.ports import (
    AvatarSessionRecord,
    DeviceBinding,
    EvidenceIndexRow,
    ThreadRecord,
    TurnRecord,
)

SessionFactory = async_sessionmaker[AsyncSession]


def _encode_cursor(created_at: datetime, ident: str) -> str:
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{ident}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts, ident = raw.split("|", 1)
    return datetime.fromisoformat(ts), ident


class _Base:
    def __init__(self, sessions: SessionFactory, *, service_identity: str) -> None:
        self._sessions = sessions
        self._identity = service_identity

    def _scope(self, client_id: str | None = None):  # type: ignore[no-untyped-def]
        session = self._sessions()

        class _Ctx:
            async def __aenter__(inner) -> AsyncSession:  # noqa: N805
                inner._cm = identity_scope(
                    session, client_id=client_id, service_identity=self._identity
                )
                return await inner._cm.__aenter__()

            async def __aexit__(inner, *exc: Any) -> None:  # noqa: N805
                try:
                    await inner._cm.__aexit__(*exc)
                finally:
                    await session.close()

        return _Ctx()


class SqlThreadRepository(_Base):
    def __init__(
        self,
        sessions: SessionFactory,
        *,
        service_identity: str,
        engine: AsyncEngine,
        salt: str = "thread",
    ) -> None:
        super().__init__(sessions, service_identity=service_identity)
        self._engine = engine
        self._salt = salt

    async def get_or_create(self, *, client_id: str, channel: str) -> ThreadRecord:
        # One thread per client; ``channel`` records where it started, not who
        # it belongs to (persistence/thread_id.py).
        thread_id = derive_thread_id(client_id, salt=self._salt)
        async with self._scope(client_id) as s:
            stmt = (
                insert(m.Thread)
                .values(
                    thread_id=thread_id,
                    client_id=client_id,
                    channel=channel,
                    created_at=datetime.now(UTC),
                    frozen=False,
                    turn_count=0,
                )
                .on_conflict_do_nothing(index_elements=["thread_id"])
            )
            await s.execute(stmt)
            row = (
                await s.execute(select(m.Thread).where(m.Thread.thread_id == thread_id))
            ).scalar_one()
            return _thread(row)

    async def get(self, thread_id: str) -> ThreadRecord | None:
        async with self._scope() as s:
            row = (
                await s.execute(select(m.Thread).where(m.Thread.thread_id == thread_id))
            ).scalar_one_or_none()
            return _thread(row) if row else None

    async def append_turn(self, turn: TurnRecord) -> None:
        async with self._scope() as s:
            thread = (
                await s.execute(select(m.Thread).where(m.Thread.thread_id == turn.thread_id))
            ).scalar_one()
            s.add(
                m.Turn(
                    turn_id=turn.turn_id,
                    thread_id=turn.thread_id,
                    client_id=thread.client_id,
                    created_at=turn.created_at,
                    channel=turn.channel,
                    client_text=turn.client_text,
                    speech=turn.speech,
                    ui_payload=turn.ui_payload,
                    evidence_id=turn.evidence_id,
                    service_type=turn.service_type,
                    intent=turn.intent,
                    error_code=turn.error_code,
                )
            )
            await s.execute(
                update(m.Thread)
                .where(m.Thread.thread_id == turn.thread_id)
                .values(turn_count=m.Thread.turn_count + 1)
            )

    async def list_turns(
        self, *, thread_id: str, cursor: str | None, limit: int
    ) -> tuple[list[TurnRecord], str | None]:
        async with self._scope() as s:
            stmt = select(m.Turn).where(m.Turn.thread_id == thread_id)
            if cursor:
                after_ts, after_id = _decode_cursor(cursor)
                stmt = stmt.where(
                    (m.Turn.created_at > after_ts)
                    | ((m.Turn.created_at == after_ts) & (m.Turn.turn_id > after_id))
                )
            stmt = stmt.order_by(m.Turn.created_at, m.Turn.turn_id).limit(limit + 1)
            rows = list((await s.execute(stmt)).scalars())
        page = rows[:limit]
        next_cursor = (
            _encode_cursor(page[-1].created_at, page[-1].turn_id) if len(rows) > limit else None
        )
        return [_turn(r) for r in page], next_cursor

    async def set_frozen(self, thread_id: str, *, frozen: bool) -> None:
        async with self._scope() as s:
            await s.execute(
                update(m.Thread).where(m.Thread.thread_id == thread_id).values(frozen=frozen)
            )

    async def list_for_client(self, client_id: str) -> list[ThreadRecord]:
        async with self._scope(client_id) as s:
            rows = (
                await s.execute(select(m.Thread).where(m.Thread.client_id == client_id))
            ).scalars()
            return [_thread(r) for r in rows]

    async def health(self) -> bool:
        return await db_health(self._engine)


def _thread(row: m.Thread) -> ThreadRecord:
    return ThreadRecord(
        thread_id=row.thread_id,
        client_id=row.client_id,
        channel=row.channel,
        created_at=row.created_at,
        frozen=row.frozen,
        turn_count=row.turn_count,
    )


def _turn(row: m.Turn) -> TurnRecord:
    return TurnRecord(
        turn_id=row.turn_id,
        thread_id=row.thread_id,
        created_at=row.created_at,
        channel=row.channel,
        client_text=row.client_text,
        speech=row.speech,
        ui_payload=list(row.ui_payload or []),
        evidence_id=row.evidence_id,
        service_type=row.service_type,
        intent=row.intent,
        error_code=row.error_code,
    )


class SqlConsentRepository(_Base):
    async def list_for_client(self, client_id: str) -> list[ConsentRecord]:
        async with self._scope(client_id) as s:
            rows = (
                await s.execute(
                    select(m.ConsentRecordRow)
                    .where(m.ConsentRecordRow.client_id == client_id)
                    .order_by(m.ConsentRecordRow.granted_at)
                )
            ).scalars()
            return [_consent(r) for r in rows]

    async def record(self, consent: ConsentRecord) -> None:
        async with self._scope(consent.client_id) as s:
            s.add(
                m.ConsentRecordRow(
                    client_id=consent.client_id,
                    type=str(consent.type),
                    version=consent.version,
                    granted=consent.granted,
                    granted_at=consent.granted_at,
                    revoked_at=consent.revoked_at,
                    channel=consent.channel,
                )
            )

    async def revoke(self, *, client_id: str, type: ConsentType, at: datetime) -> bool:
        async with self._scope(client_id) as s:
            result = await s.execute(
                update(m.ConsentRecordRow)
                .where(
                    m.ConsentRecordRow.client_id == client_id,
                    m.ConsentRecordRow.type == str(type),
                    m.ConsentRecordRow.granted.is_(True),
                    m.ConsentRecordRow.revoked_at.is_(None),
                )
                .values(revoked_at=at)
            )
            return (result.rowcount or 0) > 0

    async def has_active(self, *, client_id: str, type: ConsentType, version: str | None) -> bool:
        async with self._scope(client_id) as s:
            stmt = (
                select(func.count())
                .select_from(m.ConsentRecordRow)
                .where(
                    m.ConsentRecordRow.client_id == client_id,
                    m.ConsentRecordRow.type == str(type),
                    m.ConsentRecordRow.granted.is_(True),
                    m.ConsentRecordRow.revoked_at.is_(None),
                )
            )
            if version is not None:
                stmt = stmt.where(m.ConsentRecordRow.version == version)
            return int((await s.execute(stmt)).scalar_one()) > 0


def _consent(row: m.ConsentRecordRow) -> ConsentRecord:
    return ConsentRecord(
        client_id=row.client_id,
        type=ConsentType(row.type),
        version=row.version,
        granted=row.granted,
        granted_at=row.granted_at,
        revoked_at=row.revoked_at,
        channel=row.channel,
    )


class SqlDeviceRepository(_Base):
    async def get(self, *, client_id: str, jkt: str) -> DeviceBinding | None:
        async with self._scope(client_id) as s:
            row = (
                await s.execute(
                    select(m.DeviceBinding).where(
                        m.DeviceBinding.client_id == client_id, m.DeviceBinding.jkt == jkt
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return DeviceBinding(
                client_id=row.client_id,
                device_id=row.device_id,
                jkt=row.jkt,
                public_key_jwk=row.public_key_jwk,
                registered_at=row.registered_at,
                attestation_verified=row.attestation_verified,
            )

    async def register(self, binding: DeviceBinding) -> None:
        async with self._scope(binding.client_id) as s:
            stmt = (
                insert(m.DeviceBinding)
                .values(
                    client_id=binding.client_id,
                    device_id=binding.device_id,
                    jkt=binding.jkt,
                    public_key_jwk=binding.public_key_jwk,
                    registered_at=binding.registered_at,
                    attestation_verified=binding.attestation_verified,
                )
                .on_conflict_do_update(
                    index_elements=["client_id", "jkt"],
                    set_={
                        "public_key_jwk": binding.public_key_jwk,
                        "device_id": binding.device_id,
                        "attestation_verified": binding.attestation_verified,
                    },
                )
            )
            await s.execute(stmt)


class SqlFormSpecRepository(_Base):
    async def store(self, spec: FormSpec, *, status: str) -> None:
        async with self._scope(spec.client_id) as s:
            s.add(
                m.FormSpecRow(
                    form_id=spec.form_id,
                    client_id=spec.client_id,
                    thread_id=spec.thread_id,
                    turn_id=spec.turn_id,
                    spec=spec.model_dump(mode="json"),
                    signature=spec.signature,
                    expires_at=spec.expires_at,
                    status=status,
                    created_at=datetime.now(UTC),
                )
            )

    async def get(self, form_id: str) -> tuple[FormSpec, str] | None:
        async with self._scope() as s:
            row = (
                await s.execute(select(m.FormSpecRow).where(m.FormSpecRow.form_id == form_id))
            ).scalar_one_or_none()
            if row is None:
                return None
            return FormSpec.model_validate(row.spec), row.status

    async def mark(self, form_id: str, *, status: str) -> None:
        async with self._scope() as s:
            await s.execute(
                update(m.FormSpecRow).where(m.FormSpecRow.form_id == form_id).values(status=status)
            )

    async def record_submission(
        self,
        *,
        form_id: str,
        client_id: str,
        values: dict[str, Any],
        acknowledgements: list[str],
        disclosure_versions: dict[str, str],
        step_up_challenge_id: str,
        order_id: str | None,
        idempotency_key: str,
    ) -> None:
        async with self._scope(client_id) as s:
            s.add(
                m.FormSubmission(
                    form_id=form_id,
                    client_id=client_id,
                    values=values,
                    acknowledgements=acknowledgements,
                    disclosure_versions=disclosure_versions,
                    step_up_challenge_id=step_up_challenge_id,
                    order_id=order_id,
                    idempotency_key=idempotency_key,
                    submitted_at=datetime.now(UTC),
                )
            )


class SqlIdempotencyRepository(_Base):
    async def get(self, key: str) -> tuple[str, dict[str, Any]] | None:
        async with self._scope() as s:
            row = (
                await s.execute(select(m.IdempotencyKey).where(m.IdempotencyKey.key == key))
            ).scalar_one_or_none()
            if row is None or row.expires_at < datetime.now(UTC):
                return None
            return row.request_hash, dict(row.response)

    async def put(
        self, key: str, *, request_hash: str, response: dict[str, Any], ttl_s: int
    ) -> None:
        async with self._scope() as s:
            stmt = (
                insert(m.IdempotencyKey)
                .values(
                    key=key,
                    request_hash=request_hash,
                    response=response,
                    expires_at=datetime.now(UTC) + timedelta(seconds=ttl_s),
                )
                .on_conflict_do_nothing(index_elements=["key"])
            )
            await s.execute(stmt)


class SqlChallengeRepository(_Base):
    async def store(
        self,
        *,
        challenge_id: str,
        client_id: str,
        form_id: str,
        amount_hash: str,
        nonce: str,
        expires_at: datetime,
    ) -> None:
        async with self._scope(client_id) as s:
            s.add(
                m.StepUpChallengeRow(
                    challenge_id=challenge_id,
                    client_id=client_id,
                    form_id=form_id,
                    amount_hash=amount_hash,
                    nonce=nonce,
                    expires_at=expires_at,
                )
            )

    async def consume(self, *, challenge_id: str, client_id: str) -> dict[str, Any] | None:
        async with self._scope(client_id) as s:
            result = await s.execute(
                update(m.StepUpChallengeRow)
                .where(
                    m.StepUpChallengeRow.challenge_id == challenge_id,
                    m.StepUpChallengeRow.client_id == client_id,
                    m.StepUpChallengeRow.used_at.is_(None),
                )
                .values(used_at=datetime.now(UTC))
                .returning(m.StepUpChallengeRow)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return {
                "challenge_id": row.challenge_id,
                "client_id": row.client_id,
                "form_id": row.form_id,
                "amount_hash": row.amount_hash,
                "nonce": row.nonce,
                "expires_at": row.expires_at.isoformat(),
                "used_at": row.used_at.isoformat() if row.used_at else None,
            }


class SqlAvatarSessionRepository(_Base):
    async def create(self, record: AvatarSessionRecord) -> None:
        async with self._scope(record.client_id) as s:
            s.add(
                m.AvatarSession(
                    avatar_session_id=record.avatar_session_id,
                    client_id=record.client_id,
                    thread_id=record.thread_id,
                    vendor_session_id=record.vendor_session_id,
                    started_at=record.started_at,
                    ended_at=record.ended_at,
                    duration_s=record.duration_s,
                    speaking_s=record.speaking_s,
                    end_reason=record.end_reason,
                )
            )

    async def finish(
        self,
        avatar_session_id: str,
        *,
        ended_at: datetime,
        duration_s: float,
        speaking_s: float,
        end_reason: str,
    ) -> None:
        async with self._scope() as s:
            await s.execute(
                update(m.AvatarSession)
                .where(m.AvatarSession.avatar_session_id == avatar_session_id)
                .values(
                    ended_at=ended_at,
                    duration_s=duration_s,
                    speaking_s=speaking_s,
                    end_reason=end_reason,
                )
            )

    async def minutes_used_today(self, client_id: str) -> float:
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        async with self._scope(client_id) as s:
            rows = (
                await s.execute(
                    select(m.AvatarSession).where(
                        m.AvatarSession.client_id == client_id, m.AvatarSession.started_at >= start
                    )
                )
            ).scalars()
            seconds = 0.0
            now = datetime.now(UTC)
            for r in rows:
                seconds += r.duration_s if r.ended_at else (now - r.started_at).total_seconds()
            return seconds / 60

    async def get(self, avatar_session_id: str) -> AvatarSessionRecord | None:
        async with self._scope() as s:
            row = (
                await s.execute(
                    select(m.AvatarSession).where(
                        m.AvatarSession.avatar_session_id == avatar_session_id
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return AvatarSessionRecord(
                avatar_session_id=row.avatar_session_id,
                client_id=row.client_id,
                thread_id=row.thread_id,
                vendor_session_id=row.vendor_session_id,
                started_at=row.started_at,
                ended_at=row.ended_at,
                duration_s=row.duration_s,
                speaking_s=row.speaking_s,
                end_reason=row.end_reason,
            )


class SqlEvidenceIndexRepository(_Base):
    async def index(self, row: EvidenceIndexRow) -> None:
        async with self._scope(row.client_id) as s:
            stmt = (
                insert(m.EvidenceIndex)
                .values(
                    evidence_id=row.evidence_id,
                    client_id=row.client_id,
                    thread_id=row.thread_id,
                    turn_id=row.turn_id,
                    created_at=row.created_at,
                    service_type=row.service_type,
                    service_subtype=row.service_subtype,
                    intent=row.intent,
                    product_ids=row.product_ids,
                    object_key=row.object_key,
                    content_hash=row.content_hash,
                    legal_hold=row.legal_hold,
                    refused=row.refused,
                )
                .on_conflict_do_nothing(index_elements=["evidence_id"])
            )
            await s.execute(stmt)

    async def query(
        self,
        *,
        client_id: str | None,
        thread_id: str | None,
        since: datetime | None,
        until: datetime | None,
        service_type: str | None,
        product_id: str | None,
        refused: bool | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[EvidenceIndexRow], str | None]:
        async with self._scope(client_id) as s:
            stmt = select(m.EvidenceIndex)
            if client_id is not None:
                stmt = stmt.where(m.EvidenceIndex.client_id == client_id)
            if thread_id is not None:
                stmt = stmt.where(m.EvidenceIndex.thread_id == thread_id)
            if since is not None:
                stmt = stmt.where(m.EvidenceIndex.created_at >= since)
            if until is not None:
                stmt = stmt.where(m.EvidenceIndex.created_at <= until)
            if service_type is not None:
                stmt = stmt.where(m.EvidenceIndex.service_type == service_type)
            if product_id is not None:
                stmt = stmt.where(m.EvidenceIndex.product_ids.contains([product_id]))
            if refused is not None:
                stmt = stmt.where(m.EvidenceIndex.refused.is_(refused))
            if cursor:
                after_ts, after_id = _decode_cursor(cursor)
                stmt = stmt.where(
                    (m.EvidenceIndex.created_at > after_ts)
                    | (
                        (m.EvidenceIndex.created_at == after_ts)
                        & (m.EvidenceIndex.evidence_id > after_id)
                    )
                )
            stmt = stmt.order_by(m.EvidenceIndex.created_at, m.EvidenceIndex.evidence_id).limit(
                limit + 1
            )
            rows = list((await s.execute(stmt)).scalars())
        page = rows[:limit]
        next_cursor = (
            _encode_cursor(page[-1].created_at, page[-1].evidence_id) if len(rows) > limit else None
        )
        return [_evidence(r) for r in page], next_cursor

    async def get(self, evidence_id: str) -> EvidenceIndexRow | None:
        async with self._scope() as s:
            row = (
                await s.execute(
                    select(m.EvidenceIndex).where(m.EvidenceIndex.evidence_id == evidence_id)
                )
            ).scalar_one_or_none()
            return _evidence(row) if row else None

    async def set_legal_hold(self, *, thread_id: str, on: bool) -> int:
        async with self._scope() as s:
            result = await s.execute(
                update(m.EvidenceIndex)
                .where(m.EvidenceIndex.thread_id == thread_id)
                .values(legal_hold=on)
            )
            return int(result.rowcount or 0)

    async def counts(self, *, since: datetime, until: datetime) -> dict[str, Any]:
        async with self._scope() as s:
            base = select(m.EvidenceIndex).where(
                m.EvidenceIndex.created_at >= since, m.EvidenceIndex.created_at <= until
            )
            total = int(
                (await s.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
            )
            by_service = (
                await s.execute(
                    select(m.EvidenceIndex.service_type, func.count())
                    .where(m.EvidenceIndex.created_at >= since, m.EvidenceIndex.created_at <= until)
                    .group_by(m.EvidenceIndex.service_type)
                )
            ).all()
            by_intent = (
                await s.execute(
                    select(m.EvidenceIndex.intent, func.count())
                    .where(m.EvidenceIndex.created_at >= since, m.EvidenceIndex.created_at <= until)
                    .group_by(m.EvidenceIndex.intent)
                )
            ).all()
            refused = int(
                (
                    await s.execute(
                        select(func.count())
                        .select_from(m.EvidenceIndex)
                        .where(
                            m.EvidenceIndex.created_at >= since,
                            m.EvidenceIndex.created_at <= until,
                            m.EvidenceIndex.refused.is_(True),
                        )
                    )
                ).scalar_one()
            )
        return {
            "evidence_records": total,
            "turns_by_service_type": {k: int(v) for k, v in by_service},
            "turns_by_intent": {k: int(v) for k, v in by_intent},
            "refusals": refused,
        }


def _evidence(row: m.EvidenceIndex) -> EvidenceIndexRow:
    return EvidenceIndexRow(
        evidence_id=row.evidence_id,
        client_id=row.client_id,
        thread_id=row.thread_id,
        turn_id=row.turn_id,
        created_at=row.created_at,
        service_type=row.service_type,
        service_subtype=row.service_subtype,
        intent=row.intent,
        product_ids=list(row.product_ids or []),
        object_key=row.object_key,
        content_hash=row.content_hash,
        legal_hold=row.legal_hold,
        refused=row.refused,
    )


class SqlAccessLogRepository(_Base):
    async def log(self, *, actor: str, action: str, scope: dict[str, Any], reason: str) -> None:
        async with self._scope() as s:
            s.add(
                m.AccessLog(
                    at=datetime.now(UTC), actor=actor, action=action, scope=scope, reason=reason
                )
            )


class SqlArcoRepository(_Base):
    async def open_request(
        self, *, request_id: str, client_id: str, kind: str, opened_at: datetime
    ) -> None:
        async with self._scope(client_id) as s:
            s.add(
                m.ArcoRequestRow(
                    request_id=request_id, client_id=client_id, kind=kind, opened_at=opened_at
                )
            )

    async def close_request(
        self, *, request_id: str, closed_at: datetime, export_key: str | None
    ) -> None:
        async with self._scope() as s:
            await s.execute(
                update(m.ArcoRequestRow)
                .where(m.ArcoRequestRow.request_id == request_id)
                .values(closed_at=closed_at, export_key=export_key)
            )

    async def list_requests(self, *, client_id: str | None) -> list[dict[str, Any]]:
        async with self._scope(client_id) as s:
            stmt = select(m.ArcoRequestRow)
            if client_id is not None:
                stmt = stmt.where(m.ArcoRequestRow.client_id == client_id)
            rows = (await s.execute(stmt.order_by(m.ArcoRequestRow.opened_at))).scalars()
            return [
                {
                    "request_id": r.request_id,
                    "client_id": r.client_id,
                    "kind": r.kind,
                    "opened_at": r.opened_at,
                    "closed_at": r.closed_at,
                    "export_key": r.export_key,
                }
                for r in rows
            ]


class SqlRulesetRepository(_Base):
    async def record_version(
        self, *, version: int, rules: list[dict[str, Any]], published_at: datetime
    ) -> None:
        async with self._scope() as s:
            # Append-only: an existing version is never updated.
            stmt = (
                insert(m.SuitabilityRuleset)
                .values(version=version, published_at=published_at, rules=rules)
                .on_conflict_do_nothing(index_elements=["version"])
            )
            await s.execute(stmt)

    async def list_versions(self) -> list[int]:
        async with self._scope() as s:
            return [
                int(v)
                for v in (
                    await s.execute(
                        select(m.SuitabilityRuleset.version).order_by(m.SuitabilityRuleset.version)
                    )
                ).scalars()
            ]


class SqlAudioSegmentRepository(_Base):
    async def record(
        self,
        *,
        thread_id: str,
        turn_id: str,
        segment_id: str,
        object_key: str,
        speaker: str,
        consent_version: str,
        created_at: datetime,
    ) -> None:
        async with self._scope() as s:
            s.add(
                m.AudioSegment(
                    segment_id=segment_id,
                    thread_id=thread_id,
                    turn_id=turn_id,
                    object_key=object_key,
                    speaker=speaker,
                    consent_version=consent_version,
                    created_at=created_at,
                )
            )

    async def count_without_consent(self) -> int:
        async with self._scope() as s:
            return int(
                (
                    await s.execute(
                        select(func.count())
                        .select_from(m.AudioSegment)
                        .where(m.AudioSegment.consent_version == "")
                    )
                ).scalar_one()
            )


class SqlChainStore(_Base):
    async def head_hash(self, thread_id: str) -> str | None:
        async with self._scope() as s:
            row = (
                await s.execute(select(m.ChainHead).where(m.ChainHead.thread_id == thread_id))
            ).scalar_one_or_none()
            return row.content_hash if row else None

    async def set_head(self, thread_id: str, content_hash: str, evidence_id: str) -> None:
        async with self._scope() as s:
            stmt = (
                insert(m.ChainHead)
                .values(
                    thread_id=thread_id,
                    content_hash=content_hash,
                    evidence_id=evidence_id,
                    updated_at=datetime.now(UTC),
                )
                .on_conflict_do_update(
                    index_elements=["thread_id"],
                    set_={
                        "content_hash": content_hash,
                        "evidence_id": evidence_id,
                        "updated_at": datetime.now(UTC),
                    },
                )
            )
            await s.execute(stmt)

    async def all_heads(self) -> dict[str, str]:
        async with self._scope() as s:
            rows = (await s.execute(select(m.ChainHead))).scalars()
            return {r.thread_id: r.content_hash for r in rows}


class SqlSpool(_Base):
    async def enqueue(self, record: dict[str, Any]) -> None:
        async with self._scope() as s:
            s.add(m.EvidenceSpool(record=record, enqueued_at=datetime.now(UTC), attempts=0))

    async def dequeue(self, limit: int) -> list[tuple[int, dict[str, Any]]]:
        async with self._scope() as s:
            rows = (
                await s.execute(select(m.EvidenceSpool).order_by(m.EvidenceSpool.id).limit(limit))
            ).scalars()
            out = [(r.id, dict(r.record)) for r in rows]
            if out:
                await s.execute(
                    update(m.EvidenceSpool)
                    .where(m.EvidenceSpool.id.in_([i for i, _ in out]))
                    .values(attempts=m.EvidenceSpool.attempts + 1)
                )
            return out

    async def ack(self, ids: list[int]) -> None:
        async with self._scope() as s:
            await s.execute(delete(m.EvidenceSpool).where(m.EvidenceSpool.id.in_(ids)))

    async def depth(self) -> int:
        async with self._scope() as s:
            return int(
                (await s.execute(select(func.count()).select_from(m.EvidenceSpool))).scalar_one()
            )


async def run_retention(engine: AsyncEngine, *, days: int = 180) -> dict[str, int]:
    """Operational retention for checkpoints/threads (docs/07-data-governance/02).
    Evidence is never touched here - it expires from WORM on its own schedule."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with engine.begin() as conn:
        turns = await conn.execute(
            text("DELETE FROM session.turns WHERE created_at < :cutoff"), {"cutoff": cutoff}
        )
        threads = await conn.execute(
            text("DELETE FROM session.threads WHERE created_at < :cutoff AND turn_count = 0"),
            {"cutoff": cutoff},
        )
        checkpoints = 0
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                result = await conn.execute(
                    text(
                        f"DELETE FROM {table} WHERE thread_id IN (SELECT thread_id FROM session.threads WHERE created_at < :cutoff)"
                    ),
                    {"cutoff": cutoff},
                )
                checkpoints += int(result.rowcount or 0)
            except Exception:
                continue
    return {
        "turns": int(turns.rowcount or 0),
        "threads": int(threads.rowcount or 0),
        "checkpoints": checkpoints,
    }


RepositoryFactory = Callable[[SessionFactory, str], Any]
