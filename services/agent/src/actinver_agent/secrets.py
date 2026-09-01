"""Secret resolution by reference.

The environment carries references, never values (docs/04-backend/01 §6,
docs/05-security/04 §4). Supported schemes:

* ``secretsmanager://<name>`` - AWS Secrets Manager (floci locally).
* ``kms://<name>``            - HMAC key material. Locally it is stored as a
  Secrets Manager secret under the same name; in production the External
  Secrets Operator materialises it from KMS-backed storage.
* ``file://<relative path>``  - a file mounted by the External Secrets Operator.
* ``env://<VAR>``             - local development only.

Resolved values are held in memory and never logged. ``assert_not_a_secret``
implements the startup assertion that catches a key pasted where a reference
belongs.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

from actinver_agent.config import Environment, Settings

_REFERENCE_SCHEMES = ("secretsmanager://", "kms://", "file://", "env://")
_KNOWN_SECRET_PREFIXES = ("sk-", "AKIA", "ghp_", "xoxb-", "AIza", "ya29.", "hg_", "la_")


class SecretResolutionError(RuntimeError):
    pass


class SecretBackend(Protocol):
    async def get(self, name: str) -> str: ...


class SecretResolver:
    def __init__(
        self,
        *,
        settings: Settings,
        manager: SecretBackend | None,
        file_root: Path | None = None,
    ) -> None:
        self._settings = settings
        self._manager = manager
        self._file_root = file_root or Path(settings.secrets.file_root)
        self._cache: dict[str, str] = {}

    async def resolve(self, reference: str) -> str:
        if not reference:
            raise SecretResolutionError("empty secret reference")
        if reference in self._cache:
            return self._cache[reference]
        value = await self._resolve_uncached(reference)
        self._cache[reference] = value
        return value

    async def resolve_bytes(self, reference: str) -> bytes:
        return (await self.resolve(reference)).encode("utf-8")

    async def try_resolve(self, reference: str) -> str | None:
        try:
            return await self.resolve(reference)
        except SecretResolutionError:
            return None

    async def _resolve_uncached(self, reference: str) -> str:
        if reference.startswith("env://"):
            if self._settings.environment is not Environment.LOCAL:
                raise SecretResolutionError("env:// references are local-only")
            name = reference.removeprefix("env://")
            value = os.environ.get(name)
            if value is None:
                raise SecretResolutionError(f"environment variable {name} is not set")
            return value
        if reference.startswith("file://"):
            path = self._file_root / reference.removeprefix("file://")
            try:
                return path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise SecretResolutionError(f"cannot read secret file {path.name}") from exc
        if reference.startswith(("secretsmanager://", "kms://")):
            if self._manager is None:
                raise SecretResolutionError("no secrets-manager backend configured")
            name = re.sub(r"^[a-z]+://", "", reference)
            try:
                return await self._manager.get(name)
            except Exception as exc:
                raise SecretResolutionError(f"secret {name!r} unavailable") from exc
        raise SecretResolutionError(f"unsupported secret reference scheme in {reference!r}")


def looks_like_secret(value: str) -> bool:
    """Heuristic used by the startup assertion.

    A reference is fine. A short word is fine. A long high-entropy token or a
    string with a well-known credential prefix is not.
    """
    if not value or value.startswith(_REFERENCE_SCHEMES):
        return False
    if value.startswith(_KNOWN_SECRET_PREFIXES):
        return True
    if len(value) < 24 or " " in value:
        return False
    if re.fullmatch(r"[A-Za-z0-9+/=_\-.]+", value) is None:
        return False
    return _shannon_entropy(value) > 4.0


def _shannon_entropy(value: str) -> float:
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    length = len(value)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def assert_not_a_secret(name: str, value: str) -> None:
    if looks_like_secret(value):
        raise RuntimeError(
            f"configuration value {name} looks like a secret; the environment must carry "
            "references (secretsmanager://, kms://, file://), not values"
        )


def assert_reference_fields(settings: Settings) -> None:
    """Fail the pod if a ``*_ref`` field carries a value instead of a reference."""
    checks: list[tuple[str, str]] = [
        ("LIVEAVATAR_API_KEY_REF", settings.avatar.api_key_ref),
        ("FORM_SPEC_SIGNING_KEY_REF", settings.form_spec_signing_key_ref),
        ("SUITABILITY_SIGNING_KEY_REF", settings.suitability_signing_key_ref),
        ("AUTH_DEV_SIGNING_KEY_REF", settings.auth.dev_signing_key_ref),
        ("LLM_GEMINI_API_KEY_REF", settings.llm.gemini_api_key_ref),
        ("OBJECT_STORE_ACCESS_KEY_REF", settings.object_store.access_key_ref),
        ("OBJECT_STORE_SECRET_KEY_REF", settings.object_store.secret_key_ref),
        ("CLIENT_HASH_SALT_REF", settings.client_hash_salt_ref),
    ]
    for name, value in checks:
        if value and not value.startswith(_REFERENCE_SCHEMES):
            raise RuntimeError(f"{name} must be a secret reference, got a literal value")
        assert_not_a_secret(name, value)


ResolveFn = Callable[[str], Awaitable[str]]
