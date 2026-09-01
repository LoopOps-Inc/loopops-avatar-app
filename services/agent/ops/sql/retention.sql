-- Operational retention (docs/07-data-governance/02 §1):
--   LangGraph checkpoints ......... 180 days (partition detach + crypto erasure)
--   threads / turns / avatar_sessions 180 days
--   idempotency keys .............. 24 h (expires_at)
--   step-up challenges ............ 120 s (expires_at)
-- Evidence records, transcripts, audio and form specs are NEVER touched here:
-- they expire from the WORM store on their own five-year schedule and produce
-- a logged certificate of destruction.
--
-- Run daily (cron / Kubernetes CronJob) as the `agent_svc` role. Equivalent
-- Python entrypoint: `actinver-agent retention --days 180`.

BEGIN;

DELETE FROM txn.step_up_challenges WHERE expires_at < now() - interval '1 day';
DELETE FROM txn.idempotency_keys   WHERE expires_at < now();

DELETE FROM session.turns           WHERE created_at < now() - interval '180 days';
DELETE FROM session.avatar_sessions WHERE started_at < now() - interval '180 days';
DELETE FROM session.threads         WHERE created_at < now() - interval '180 days' AND turn_count = 0;

-- Checkpoints: prefer partition detach (see checkpoint_partitioning.sql). Row
-- deletion is the fallback for unpartitioned local databases only.
DELETE FROM checkpoint_writes WHERE thread_id IN (
  SELECT thread_id FROM session.threads WHERE created_at < now() - interval '180 days');
DELETE FROM checkpoint_blobs  WHERE thread_id IN (
  SELECT thread_id FROM session.threads WHERE created_at < now() - interval '180 days');
DELETE FROM checkpoints       WHERE thread_id IN (
  SELECT thread_id FROM session.threads WHERE created_at < now() - interval '180 days');

COMMIT;
