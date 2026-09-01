"""Every configuration field is documented in the example environment file with
its pydantic-settings prefix, so a deployment cannot silently rely on a default
nobody wrote down (docs/04-backend/01 §6)."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic_settings import BaseSettings

from actinver_agent import config

_NESTED_PREFIXES: dict[str, str] = {
    "auth": "AUTH_",
    "llm": "LLM_",
    "vertex": "VERTEX_",
    "avatar": "LIVEAVATAR_",
    "voice": "VOICE_",
    "limits": "LIMITS_",
    "services": "SVC_",
    "object_store": "OBJECT_STORE_",
    "secrets": "SECRETS_",
}


def _env_file(service_root: Path) -> Path:
    for name in (".env.example", "env.example"):
        candidate = service_root / name
        if candidate.exists():
            return candidate
    raise AssertionError("neither .env.example nor env.example exists")


def _declared_vars(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if match:
            names.add(match.group(1))
    return names


def _expected_vars() -> set[str]:
    expected: set[str] = set()
    for name, field in config.Settings.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseSettings):
            prefix = _NESTED_PREFIXES[name]
            expected.update(prefix + sub.upper() for sub in annotation.model_fields)
        else:
            expected.add(name.upper())
    return expected


def test_env_example_covers_every_setting(service_root: Path) -> None:
    declared = _declared_vars(_env_file(service_root))
    missing = sorted(_expected_vars() - declared)
    assert not missing, "settings missing from the example env file: " + ", ".join(missing)


def test_env_example_carries_references_not_secrets(service_root: Path) -> None:
    from actinver_agent.secrets import looks_like_secret

    offenders: list[str] = []
    for line in _env_file(service_root).read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*?)(?:\s+#.*)?$", line)
        if not match:
            continue
        name, value = match.group(1), match.group(2).strip()
        if (
            name.endswith("_REF")
            and value
            and not value.startswith(("secretsmanager://", "kms://", "file://", "env://"))
        ):
            offenders.append(f"{name} is not a reference")
        if looks_like_secret(value):
            offenders.append(f"{name} looks like a secret value")
    assert not offenders, "\n".join(offenders)


def test_nested_prefixes_match_config() -> None:
    for name, prefix in _NESTED_PREFIXES.items():
        annotation = config.Settings.model_fields[name].annotation
        assert isinstance(annotation, type) and issubclass(annotation, BaseSettings)
        assert annotation.model_config.get("env_prefix") == prefix, (name, prefix)
