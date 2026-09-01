"""Shared paths for the build-time assertions (docs/05-security/05 §3)."""

from __future__ import annotations

from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src" / "actinver_agent"
REPO_ROOT = SERVICE_ROOT.parents[1]
WEB_SRC = REPO_ROOT / "apps" / "web" / "src"


@pytest.fixture(scope="session")
def service_root() -> Path:
    return SERVICE_ROOT


@pytest.fixture(scope="session")
def src_root() -> Path:
    return SRC_ROOT


@pytest.fixture(scope="session")
def web_src() -> Path:
    return WEB_SRC
