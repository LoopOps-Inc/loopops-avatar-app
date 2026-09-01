-- Service roles for least privilege and row-level security (docs/04-backend/02 §4,
-- docs/05-security/01 §4). Locally every process connects as `postgres`; the
-- Alembic migration binds RLS policies to `current_setting('app.client_id')`
-- and `current_setting('app.service_identity')`, which repositories SET per
-- transaction. These roles exist so the same migration can GRANT per service
-- and so a deployment can hand each container its own credential.
-- Idempotent: safe to re-run on every container start.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_svc') THEN
    CREATE ROLE agent_svc LOGIN PASSWORD 'local_only_not_a_secret';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_svc') THEN
    CREATE ROLE audit_svc LOGIN PASSWORD 'local_only_not_a_secret';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'txn_svc') THEN
    CREATE ROLE txn_svc LOGIN PASSWORD 'local_only_not_a_secret';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'suitability_svc') THEN
    CREATE ROLE suitability_svc LOGIN PASSWORD 'local_only_not_a_secret';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_ro') THEN
    CREATE ROLE compliance_ro LOGIN PASSWORD 'local_only_not_a_secret';
  END IF;
END
$$;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
