"""Egress-proxy DLP ruleset, generated from ``patterns.py``.

One source, no divergence (docs/01-architecture/02 §5, RB-06). The proxy's
inline detector and ``compliance_guard`` cannot disagree because both derive
from the same module.
"""

from __future__ import annotations

from typing import Any

import orjson

from actinver_agent.guardrails import patterns as pat

#: Identifier classes the proxy blocks on bodies destined for LiveAvatar and
#: Vertex AI (infra/terraform/egress-allowlist.tf: dlp_block_pattern_classes).
DLP_BLOCK_CLASSES: tuple[str, ...] = ("RFC", "CURP", "CLABE", "PAN", "CONTRACT")


def export_dlp_ruleset() -> dict[str, Any]:
    return {
        "source": "actinver_agent.guardrails.patterns",
        "block_classes": list(DLP_BLOCK_CLASSES),
        "identifier_patterns": {
            name: pattern.pattern for name, pattern in pat.IDENTIFIER_PATTERNS.items()
        },
        "precise_amount_pattern": pat.PRECISE_AMOUNT.pattern,
        "spoken_long_number_pattern": pat.SPOKEN_LONG_NUMBER.pattern,
        "flags": {"ignorecase": True},
        "destinations": ["api.liveavatar.com", "*.googleapis.com"],
    }


def export_dlp_json() -> bytes:
    return orjson.dumps(export_dlp_ruleset(), option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)


def dlp_hits(body: str) -> dict[str, int]:
    """Count identifier hits on an outbound body - the proxy's inline check."""
    hits: dict[str, int] = {}
    for name in DLP_BLOCK_CLASSES:
        n = len(pat.IDENTIFIER_PATTERNS[name].findall(body))
        if n:
            hits[name] = n
    return hits
