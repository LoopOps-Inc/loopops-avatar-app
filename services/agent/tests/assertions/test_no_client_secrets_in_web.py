"""ADR-0001 / ADR-0008: the client bundle never carries the vendor API key
header, the LiveKit agent token, or the vendor API host.

Scope is ``apps/web/src/**`` (what ships to the browser). The Vite dev proxy in
``apps/web/vite.config.ts`` is server-side and is the documented local key
injector, so it is deliberately out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_FORBIDDEN = re.compile(r"X-API-KEY|livekit_agent_token|api\.liveavatar\.com")


def test_web_source_has_no_vendor_secrets(web_src: Path) -> None:
    if not web_src.exists():
        pytest.skip("apps/web/src not present in this checkout")
    hits: list[str] = []
    for path in web_src.rglob("*"):
        if not path.is_file() or path.suffix not in {
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".json",
            ".css",
            ".html",
        }:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if _FORBIDDEN.search(line):
                hits.append(f"{path.relative_to(web_src)}:{lineno}: {line.strip()[:120]}")
    assert not hits, "vendor credential/host referenced in client source:\n" + "\n".join(hits)
