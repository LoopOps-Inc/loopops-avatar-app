"""The redaction proxy in front of every model call.

It operates on the *serialised request body*, not on application objects, so a
developer cannot bypass it by constructing the prompt differently
(docs/01-architecture/04 §6, docs/06-compliance/04 §4). Its rejection list is
the same one the egress DLP uses: both derive from ``guardrails/patterns.py``.
"""

from __future__ import annotations

from typing import overload

import structlog

from actinver_agent.guardrails import patterns as pat
from actinver_agent.observability.setup import get_metrics

log = structlog.get_logger(__name__)


class RedactionViolation(RuntimeError):
    """Raised when RESTRICTED content reached the model boundary. That is a
    pipeline defect upstream, not something to paper over."""


class RedactionProxy:
    @overload
    def redact_body(self, body: bytes) -> tuple[bytes, int]: ...
    @overload
    def redact_body(self, body: str) -> tuple[str, int]: ...

    def redact_body(self, body: bytes | str) -> tuple[bytes | str, int]:
        if isinstance(body, bytes):
            text, count = pat.redact(body.decode("utf-8"))
            self._observe(count)
            return text.encode("utf-8"), count
        text, count = pat.redact(body)
        self._observe(count)
        return text, count

    def assert_clean(self, body: str, *, field: str) -> None:
        hits = pat.scan_identifiers(body)
        if hits:
            get_metrics().dlp_hits.add(1, {"stage": "redaction_proxy", "field": field})
            log.error(
                "redaction.restricted_content_at_model_boundary",
                field=field,
                classes=sorted(hits),
                security_event=True,
            )
            raise RedactionViolation(f"identifier classes {sorted(hits)} present in {field}")

    @staticmethod
    def _observe(count: int) -> None:
        if count:
            get_metrics().dlp_hits.add(count, {"stage": "redaction_proxy", "field": "body"})
            log.warning("redaction.model_request_redacted", count=count)
