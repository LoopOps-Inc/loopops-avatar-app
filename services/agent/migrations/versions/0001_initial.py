"""initial schemas, tables, roles and row-level security

Revision ID: 0001
Revises:
Create Date: 2026-09-01

Schemas per docs/01-architecture/04 §3.1 and docs/07-data-governance/03 §1.
Row-level security binds every client-scoped table to the calling identity
(``app.client_id`` / ``app.service_identity``), not to network position
(docs/04-backend/02 §4, control TO-09).

LangGraph's ``AsyncPostgresSaver`` creates its own tables (``checkpoints``,
``checkpoint_writes``, ``checkpoint_blobs``) in the public schema via
``setup()``; the monthly partitioning DDL for them is in
``ops/sql/checkpoint_partitioning.sql`` and is applied by the DBA at deploy
time, because partitioning must wrap the tables the library creates.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ("session", "txn", "catalog", "rules", "audit", "retrieval")
ROLES = ("agent_svc", "audit_svc", "txn_svc", "suitability_svc", "compliance_ro")

#: (schema, table) pairs carrying client_id → RLS enabled.
CLIENT_TABLES = (
    ("session", "threads"),
    ("session", "turns"),
    ("session", "avatar_sessions"),
    ("session", "device_bindings"),
    ("session", "consent_records"),
    ("txn", "form_specs"),
    ("txn", "form_submissions"),
    ("txn", "step_up_challenges"),
    ("audit", "evidence_index"),
    ("audit", "arco_requests"),
)

RLS_POLICY = (
    "client_id = current_setting('app.client_id', true) "
    "OR current_setting('app.service_identity', true) IN ('audit_svc','compliance_ro','txn_svc')"
)


def _ts() -> sa.types.TypeEngine:  # type: ignore[type-arg]
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── session ────────────────────────────────────────────────────────────
    op.create_table(
        "threads",
        sa.Column("thread_id", sa.String(80), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False, index=True),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("created_at", _ts(), nullable=False),
        sa.Column("frozen", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("turn_count", sa.Integer, nullable=False, server_default="0"),
        schema="session",
    )
    op.create_table(
        "turns",
        sa.Column("turn_id", sa.String(80), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(80),
            sa.ForeignKey("session.threads.thread_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(80), nullable=False, index=True),
        sa.Column("created_at", _ts(), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("client_text", sa.Text, nullable=False),
        sa.Column("speech", sa.Text, nullable=True),
        sa.Column("ui_payload", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("evidence_id", sa.String(120), nullable=True),
        sa.Column("service_type", sa.String(20), nullable=False),
        sa.Column("intent", sa.String(40), nullable=False),
        sa.Column("error_code", sa.String(60), nullable=True),
        schema="session",
    )
    op.create_index(
        "ix_session_turns_thread_created", "turns", ["thread_id", "created_at"], schema="session"
    )
    op.create_table(
        "avatar_sessions",
        sa.Column("avatar_session_id", sa.String(80), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False),
        sa.Column("thread_id", sa.String(80), nullable=False),
        sa.Column("vendor_session_id", sa.String(120), nullable=False),
        sa.Column("started_at", _ts(), nullable=False),
        sa.Column("ended_at", _ts(), nullable=True),
        sa.Column("duration_s", sa.Float, nullable=False, server_default="0"),
        sa.Column("speaking_s", sa.Float, nullable=False, server_default="0"),
        sa.Column("end_reason", sa.String(40), nullable=True),
        schema="session",
    )
    op.create_index(
        "ix_session_avatar_client_started",
        "avatar_sessions",
        ["client_id", "started_at"],
        schema="session",
    )
    op.create_table(
        "device_bindings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(80), nullable=False, index=True),
        sa.Column("device_id", sa.String(120), nullable=False),
        sa.Column("jkt", sa.String(120), nullable=False),
        sa.Column("public_key_jwk", postgresql.JSONB, nullable=False),
        sa.Column("registered_at", _ts(), nullable=False),
        sa.Column("attestation_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("client_id", "jkt"),
        schema="session",
    )
    op.create_table(
        "consent_records",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(80), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("granted", sa.Boolean, nullable=False),
        sa.Column("granted_at", _ts(), nullable=False),
        sa.Column("revoked_at", _ts(), nullable=True),
        sa.Column("channel", sa.String(10), nullable=False, server_default="app"),
        schema="session",
    )
    op.create_index(
        "ix_session_consent_client_type", "consent_records", ["client_id", "type"], schema="session"
    )

    # ── txn ────────────────────────────────────────────────────────────────
    op.create_table(
        "form_specs",
        sa.Column("form_id", sa.String(80), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False, index=True),
        sa.Column("thread_id", sa.String(80), nullable=False),
        sa.Column("turn_id", sa.String(80), nullable=False),
        sa.Column("spec", postgresql.JSONB, nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("expires_at", _ts(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ISSUED"),
        sa.Column("created_at", _ts(), nullable=False),
        schema="txn",
    )
    op.create_table(
        "form_submissions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("form_id", sa.String(80), nullable=False, index=True),
        sa.Column("client_id", sa.String(80), nullable=False, index=True),
        sa.Column("values", postgresql.JSONB, nullable=False),
        sa.Column("acknowledgements", postgresql.JSONB, nullable=False),
        sa.Column("disclosure_versions", postgresql.JSONB, nullable=False),
        sa.Column("step_up_challenge_id", sa.String(80), nullable=False),
        sa.Column("order_id", sa.String(80), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("submitted_at", _ts(), nullable=False),
        schema="txn",
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB, nullable=False),
        sa.Column("expires_at", _ts(), nullable=False),
        schema="txn",
    )
    op.create_table(
        "step_up_challenges",
        sa.Column("challenge_id", sa.String(80), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False, index=True),
        sa.Column("form_id", sa.String(80), nullable=False),
        sa.Column("amount_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("expires_at", _ts(), nullable=False),
        sa.Column("used_at", _ts(), nullable=True),
        schema="txn",
    )

    # ── catalog ────────────────────────────────────────────────────────────
    op.create_table(
        "product_cache",
        sa.Column("product_id", sa.String(40), primary_key=True),
        sa.Column("detail", postgresql.JSONB, nullable=False),
        sa.Column("refreshed_at", _ts(), nullable=False),
        schema="catalog",
    )
    op.create_table(
        "product_profile_cache",
        sa.Column("product_id", sa.String(40), primary_key=True),
        sa.Column("committee_version", sa.Integer, nullable=False),
        sa.Column("profile", postgresql.JSONB, nullable=False),
        sa.Column("refreshed_at", _ts(), nullable=False),
        schema="catalog",
    )

    # ── rules (append-only, permanent) ─────────────────────────────────────
    op.create_table(
        "suitability_rulesets",
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("published_at", _ts(), nullable=False),
        sa.Column("rules", postgresql.JSONB, nullable=False),
        schema="rules",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rules.forbid_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'suitability rulesets are append-only (ADR-0005)';
        END $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER rulesets_append_only BEFORE UPDATE OR DELETE ON rules.suitability_rulesets "
        "FOR EACH ROW EXECUTE FUNCTION rules.forbid_mutation()"
    )

    # ── audit ──────────────────────────────────────────────────────────────
    op.create_table(
        "chain_heads",
        sa.Column("thread_id", sa.String(80), primary_key=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("evidence_id", sa.String(120), nullable=False),
        sa.Column("updated_at", _ts(), nullable=False),
        schema="audit",
    )
    op.create_table(
        "spool",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("record", postgresql.JSONB, nullable=False),
        sa.Column("enqueued_at", _ts(), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        schema="audit",
    )
    op.create_table(
        "evidence_index",
        sa.Column("evidence_id", sa.String(120), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False),
        sa.Column("thread_id", sa.String(80), nullable=False),
        sa.Column("turn_id", sa.String(80), nullable=False),
        sa.Column("created_at", _ts(), nullable=False),
        sa.Column("service_type", sa.String(20), nullable=False),
        sa.Column("service_subtype", sa.String(60), nullable=False),
        sa.Column("intent", sa.String(40), nullable=False),
        sa.Column("product_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("legal_hold", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("refused", sa.Boolean, nullable=False, server_default=sa.false()),
        schema="audit",
    )
    for name, cols in (
        ("ix_audit_evidence_client_created", ["client_id", "created_at"]),
        ("ix_audit_evidence_thread_created", ["thread_id", "created_at"]),
        ("ix_audit_evidence_service_created", ["service_type", "created_at"]),
    ):
        op.create_index(name, "evidence_index", cols, schema="audit")
    op.create_table(
        "access_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", _ts(), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("scope", postgresql.JSONB, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        schema="audit",
    )
    op.create_table(
        "arco_requests",
        sa.Column("request_id", sa.String(80), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("opened_at", _ts(), nullable=False),
        sa.Column("closed_at", _ts(), nullable=True),
        sa.Column("export_key", sa.String(255), nullable=True),
        schema="audit",
    )
    op.create_table(
        "audio_segments",
        sa.Column("segment_id", sa.String(80), primary_key=True),
        sa.Column("thread_id", sa.String(80), nullable=False, index=True),
        sa.Column("turn_id", sa.String(80), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("speaker", sa.String(10), nullable=False),
        sa.Column("consent_version", sa.String(40), nullable=False),
        sa.Column("created_at", _ts(), nullable=False),
        schema="audit",
    )

    # ── retrieval (pgvector; never client data - ADR-0014) ─────────────────
    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("collection", sa.String(40), nullable=False),
        sa.Column("doc_id", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("published_at", _ts(), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding_json", postgresql.JSONB, nullable=False),
        schema="retrieval",
    )
    op.create_index("ix_retrieval_chunks_collection", "chunks", ["collection"], schema="retrieval")
    op.execute("ALTER TABLE retrieval.chunks ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX ix_retrieval_chunks_embedding ON retrieval.chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # ── roles and least privilege (docs/05-security/01 §4) ─────────────────
    for role in ROLES:
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
            f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$"
        )
    for role in ROLES:
        for schema in SCHEMAS:
            op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
    # agent: sessions, txn intake (read), catalog, retrieval; evidence only through audit_svc
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA session TO agent_svc")
    op.execute("GRANT SELECT, INSERT ON txn.form_specs TO agent_svc")
    op.execute("GRANT UPDATE (status) ON txn.form_specs TO agent_svc")
    op.execute("GRANT SELECT, INSERT, UPDATE ON txn.idempotency_keys TO agent_svc")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA catalog TO agent_svc")
    op.execute("GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA retrieval TO agent_svc")
    op.execute("GRANT SELECT ON audit.evidence_index TO agent_svc")
    op.execute("GRANT SELECT ON rules.suitability_rulesets TO agent_svc")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA session TO agent_svc")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA retrieval TO agent_svc")
    # audit: write WORM index/chain/spool/access log; cannot read conversation content
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA audit TO audit_svc")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit TO audit_svc")
    op.execute("REVOKE ALL ON session.turns FROM audit_svc")
    # txn: owns txn.*, reads device bindings, appends execution evidence via audit
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA txn TO txn_svc")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA txn TO txn_svc")
    op.execute("GRANT SELECT ON session.device_bindings TO txn_svc")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON audit.evidence_index, audit.chain_heads, audit.spool TO txn_svc"
    )
    # suitability: rulesets only
    op.execute("GRANT SELECT, INSERT ON rules.suitability_rulesets TO suitability_svc")
    # compliance console: read-only everywhere plus access-log writes
    for schema in SCHEMAS:
        op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO compliance_ro")
    op.execute("GRANT INSERT ON audit.access_log TO compliance_ro")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit TO compliance_ro")

    # ── row-level security ─────────────────────────────────────────────────
    for schema, table in CLIENT_TABLES:
        op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_client_scope ON {schema}.{table} "
            f"USING ({RLS_POLICY}) WITH CHECK ({RLS_POLICY})"
        )


def downgrade() -> None:
    # Forward-only in production; downgrade exists for local iteration only.
    for schema, table in CLIENT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_client_scope ON {schema}.{table}")
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    for role in ROLES:
        op.execute(f"DROP ROLE IF EXISTS {role}")
