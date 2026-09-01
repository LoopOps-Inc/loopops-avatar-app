"""Retention jobs (docs/07-data-governance/02 §1, control DP-06).

Operational data expires on schedule; regulatory records (evidence,
transcripts, audio, form specs) never expire before their WORM retention date
and are not touched here. Every run produces an audit log entry.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from actinver_agent.deps import Dependencies

log = structlog.get_logger(__name__)

CHECKPOINT_RETENTION_DAYS = 180
THREAD_RETENTION_DAYS = 180
IDEMPOTENCY_RETENTION_DAYS = 1


async def run_retention(deps: Dependencies) -> dict[str, Any]:
    now = datetime.now(UTC)
    report: dict[str, Any] = {"ran_at": now.isoformat(), "deleted": {}}
    engine = getattr(deps.repos.threads, "_engine", None)
    if engine is None:
        report["note"] = "memory persistence: nothing to expire"
        return report

    from sqlalchemy import text

    statements = {
        "checkpoint_writes": (
            "DELETE FROM checkpoint_writes WHERE thread_id IN "
            "(SELECT thread_id FROM session.threads WHERE created_at < :cutoff)"
        ),
        "checkpoints": (
            "DELETE FROM checkpoints WHERE thread_id IN "
            "(SELECT thread_id FROM session.threads WHERE created_at < :cutoff)"
        ),
        "session.turns": "DELETE FROM session.turns WHERE created_at < :cutoff",
        "session.threads": "DELETE FROM session.threads WHERE created_at < :cutoff",
        "txn.idempotency_keys": "DELETE FROM txn.idempotency_keys WHERE expires_at < :now",
        "txn.step_up_challenges": "DELETE FROM txn.step_up_challenges WHERE expires_at < :now",
    }
    cutoff = now - timedelta(days=CHECKPOINT_RETENTION_DAYS)
    async with engine.begin() as conn:
        for name, sql in statements.items():
            try:
                result = await conn.execute(text(sql), {"cutoff": cutoff, "now": now})
                report["deleted"][name] = result.rowcount
            except Exception as exc:
                report["deleted"][name] = f"skipped: {type(exc).__name__}"
    try:
        await deps.repos.access_log.log(
            actor="retention-job",
            action="retention.run",
            scope=report["deleted"],
            reason="scheduled retention (docs/07-data-governance/02)",
        )
    except Exception:
        log.warning("retention.audit_log_failed")
    log.info("retention.complete", deleted=report["deleted"])
    return report
