"""ADR-0011: no provider SDK import outside ``**/adapters/``.

Portability decays if unenforced; this is the CI grep the ADR calls for.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Provider SDK import roots and where each may appear.
_RULES: dict[str, tuple[str, ...]] = {
    # Google Cloud / Gemini / Vertex
    r"^\s*(?:from|import)\s+google(?:\.|\s|$)": ("adapters/",),
    r"^\s*(?:from|import)\s+langchain_google": ("adapters/",),
    # AWS
    r"^\s*(?:from|import)\s+(?:aioboto3|aiobotocore|boto3|botocore)": ("adapters/",),
    # Redis client
    r"^\s*(?:from|import)\s+redis(?:\.|\s|$)": ("adapters/redis_cache.py", "adapters/"),
    # Postgres drivers: allowed in the persistence layer and the LangGraph checkpointer wiring
    r"^\s*(?:from|import)\s+(?:psycopg|asyncpg)(?:\.|\s|$)": (
        "adapters/",
        "persistence/",
        "graph/checkpointer.py",
        "wiring.py",
    ),
    r"^\s*(?:from|import)\s+langgraph\.checkpoint\.postgres": (
        "adapters/",
        "persistence/",
        "graph/checkpointer.py",
        "wiring.py",
    ),
}


def _python_files(src_root: Path) -> list[Path]:
    return sorted(p for p in src_root.rglob("*.py") if "__pycache__" not in p.parts)


def test_provider_sdks_only_under_adapters(src_root: Path) -> None:
    violations: list[str] = []
    for path in _python_files(src_root):
        rel = path.relative_to(src_root).as_posix()
        text = path.read_text(encoding="utf-8")
        for pattern, allowed in _RULES.items():
            if not re.search(pattern, text, flags=re.MULTILINE):
                continue
            if any(rel.startswith(prefix) for prefix in allowed):
                continue
            # ``TYPE_CHECKING``-only imports are acceptable (no runtime coupling).
            if _only_under_type_checking(text, pattern):
                continue
            violations.append(f"{rel}: matches {pattern!r}, allowed under {allowed}")
    assert not violations, "provider SDK imported outside adapters:\n" + "\n".join(violations)


def _only_under_type_checking(text: str, pattern: str) -> bool:
    inside = False
    depth_marker = None
    for line in text.splitlines():
        if re.match(r"^\s*if\s+TYPE_CHECKING\s*:", line):
            inside = True
            depth_marker = len(line) - len(line.lstrip())
            continue
        if inside:
            indent = len(line) - len(line.lstrip())
            if line.strip() and depth_marker is not None and indent <= depth_marker:
                inside = False
        if re.search(pattern, line) and not inside:
            return False
    return True
