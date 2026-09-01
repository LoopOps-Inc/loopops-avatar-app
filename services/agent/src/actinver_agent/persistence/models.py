"""SQLAlchemy models for the operational schemas (docs/01-architecture/04 §3.1,
docs/07-data-governance/03 §1).

Schemas: ``session`` (threads, turns, avatar_sessions, device_bindings,
consent_records), ``txn`` (form_specs, form_submissions, idempotency_keys,
step_up_challenges), ``catalog`` (product caches), ``rules`` (append-only
rulesets), ``audit`` (chain_heads, spool, evidence_index, access_log,
arco_requests, audio_segments), ``retrieval`` (pgvector corpora).

Row-level security policies live in the Alembic migration; repositories set
``app.client_id`` / ``app.service_identity`` per transaction so the policies
bind to the calling identity, not to network position.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ── session schema ─────────────────────────────────────────────────────────────


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = ({"schema": "session"},)

    thread_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    channel: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (
        Index("ix_session_turns_thread_created", "thread_id", "created_at"),
        {"schema": "session"},
    )

    turn_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("session.threads.thread_id", ondelete="CASCADE")
    )
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(10))
    client_text: Mapped[str] = mapped_column(Text)
    speech: Mapped[str | None] = mapped_column(Text, nullable=True)
    ui_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    evidence_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    service_type: Mapped[str] = mapped_column(String(20))
    intent: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)


class AvatarSession(Base):
    __tablename__ = "avatar_sessions"
    __table_args__ = (
        Index("ix_session_avatar_client_started", "client_id", "started_at"),
        {"schema": "session"},
    )

    avatar_session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(80))
    thread_id: Mapped[str] = mapped_column(String(80))
    vendor_session_id: Mapped[str] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    speaking_s: Mapped[float] = mapped_column(Float, default=0.0)
    end_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)


class DeviceBinding(Base):
    __tablename__ = "device_bindings"
    __table_args__ = (UniqueConstraint("client_id", "jkt"), {"schema": "session"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    device_id: Mapped[str] = mapped_column(String(120))
    jkt: Mapped[str] = mapped_column(String(120))
    public_key_jwk: Mapped[dict[str, Any]] = mapped_column(JSONB)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attestation_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class ConsentRecordRow(Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        Index("ix_session_consent_client_type", "client_id", "type"),
        {"schema": "session"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(40))
    granted: Mapped[bool] = mapped_column(Boolean)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(10), default="app")


# ── txn schema ─────────────────────────────────────────────────────────────────


class FormSpecRow(Base):
    __tablename__ = "form_specs"
    __table_args__ = ({"schema": "txn"},)

    form_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    thread_id: Mapped[str] = mapped_column(String(80))
    turn_id: Mapped[str] = mapped_column(String(80))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    signature: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ISSUED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FormSubmission(Base):
    __tablename__ = "form_submissions"
    __table_args__ = ({"schema": "txn"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    form_id: Mapped[str] = mapped_column(String(80), index=True)
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB)
    acknowledgements: Mapped[list[str]] = mapped_column(JSONB)
    disclosure_versions: Mapped[dict[str, str]] = mapped_column(JSONB)
    step_up_challenge_id: Mapped[str] = mapped_column(String(80))
    order_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = ({"schema": "txn"},)

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StepUpChallengeRow(Base):
    __tablename__ = "step_up_challenges"
    __table_args__ = ({"schema": "txn"},)

    challenge_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    form_id: Mapped[str] = mapped_column(String(80))
    amount_hash: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── catalog schema ─────────────────────────────────────────────────────────────


class ProductCache(Base):
    __tablename__ = "product_cache"
    __table_args__ = ({"schema": "catalog"},)

    product_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductProfileCache(Base):
    __tablename__ = "product_profile_cache"
    __table_args__ = ({"schema": "catalog"},)

    product_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    committee_version: Mapped[int] = mapped_column(Integer)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ── rules schema (append-only, permanent) ──────────────────────────────────────


class SuitabilityRuleset(Base):
    __tablename__ = "suitability_rulesets"
    __table_args__ = ({"schema": "rules"},)

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)


# ── audit schema ───────────────────────────────────────────────────────────────


class ChainHead(Base):
    __tablename__ = "chain_heads"
    __table_args__ = ({"schema": "audit"},)

    thread_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    evidence_id: Mapped[str] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceSpool(Base):
    __tablename__ = "spool"
    __table_args__ = ({"schema": "audit"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record: Mapped[dict[str, Any]] = mapped_column(JSONB)
    enqueued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class EvidenceIndex(Base):
    __tablename__ = "evidence_index"
    __table_args__ = (
        Index("ix_audit_evidence_client_created", "client_id", "created_at"),
        Index("ix_audit_evidence_thread_created", "thread_id", "created_at"),
        Index("ix_audit_evidence_service_created", "service_type", "created_at"),
        {"schema": "audit"},
    )

    evidence_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(80))
    thread_id: Mapped[str] = mapped_column(String(80))
    turn_id: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    service_type: Mapped[str] = mapped_column(String(20))
    service_subtype: Mapped[str] = mapped_column(String(60))
    intent: Mapped[str] = mapped_column(String(40))
    product_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    object_key: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)


class AccessLog(Base):
    __tablename__ = "access_log"
    __table_args__ = ({"schema": "audit"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60))
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)


class ArcoRequestRow(Base):
    __tablename__ = "arco_requests"
    __table_args__ = ({"schema": "audit"},)

    request_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    export_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AudioSegment(Base):
    __tablename__ = "audio_segments"
    __table_args__ = ({"schema": "audit"},)

    segment_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(80), index=True)
    turn_id: Mapped[str] = mapped_column(String(80))
    object_key: Mapped[str] = mapped_column(String(255))
    speaker: Mapped[str] = mapped_column(String(10))
    consent_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ── retrieval schema (pgvector; no client data ever - ADR-0014) ───────────────


class RetrievalChunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_retrieval_chunks_collection", "collection"),
        {"schema": "retrieval"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    collection: Mapped[str] = mapped_column(String(40))
    doc_id: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    #: pgvector column is added in the migration (``vector(768)``); mapped as JSON
    #: here so the ORM stays provider-agnostic.
    embedding_json: Mapped[list[float]] = mapped_column(JSONB)
