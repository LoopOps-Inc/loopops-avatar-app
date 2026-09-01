-- Monthly partitioning of the LangGraph checkpoint tables
-- (docs/04-backend/02 §4: "Partition the checkpoint tables monthly. They grow
-- fast. Detaching a partition is instant; deleting rows is not.")
--
-- AsyncPostgresSaver.setup() creates plain tables. This script is applied ONCE
-- by the DBA after the first setup(), before production traffic. It converts
-- `checkpoints` into a range-partitioned table on a `created_at` column added
-- here, keeping the library's primary key by including created_at in it.
--
-- Retention: partitions older than 180 days (docs/01-architecture/04 §7) are
-- DETACHED and archived/cryptographically erased, never row-deleted.

BEGIN;

ALTER TABLE checkpoints ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS checkpoints_partitioned (
  LIKE checkpoints INCLUDING DEFAULTS INCLUDING CONSTRAINTS
) PARTITION BY RANGE (created_at);

-- One partition per month; create the next month ahead of time via cron.
DO $$
DECLARE
  m date := date_trunc('month', now())::date;
BEGIN
  FOR i IN 0..2 LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS checkpoints_%s PARTITION OF checkpoints_partitioned FOR VALUES FROM (%L) TO (%L)',
      to_char(m + (i || ' month')::interval, 'YYYYMM'),
      m + (i || ' month')::interval,
      m + ((i + 1) || ' month')::interval
    );
  END LOOP;
END $$;

INSERT INTO checkpoints_partitioned SELECT * FROM checkpoints;
ALTER TABLE checkpoints RENAME TO checkpoints_unpartitioned_backup;
ALTER TABLE checkpoints_partitioned RENAME TO checkpoints;

COMMIT;

-- Monthly job (example): detach partitions past the retention window.
--   ALTER TABLE checkpoints DETACH PARTITION checkpoints_202603;
--   -- archive to object storage with the retention class, then:
--   DROP TABLE checkpoints_202603;
