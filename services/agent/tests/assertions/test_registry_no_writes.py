"""ADR-0010 / control AI-05, AI-06: no tool in the registry performs a write,
and no tool argument schema accepts ``client_id``.

Skips cleanly while the tool catalogue module is not yet importable.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

import pytest

_MUTATING_VERBS = (
    "place",
    "execute",
    "buy",
    "sell",
    "transfer",
    "submit",
    "confirm",
    "cancel_order",
    "create_order",
    "update_profile",
    "set_",
    "delete",
    "withdraw",
    "deposit",
    "redeem_now",
)


def _build_registry() -> Any:
    try:
        catalog = importlib.import_module("actinver_agent.tools.catalog")
    except ImportError as exc:
        pytest.skip(f"tools.catalog not importable yet: {exc}")
    builder = getattr(catalog, "build_registry", None)
    if builder is None:
        pytest.skip("tools.catalog.build_registry not present yet")
    try:
        synthetic = importlib.import_module("actinver_agent.clients.synthetic")
    except ImportError as exc:
        pytest.skip(f"clients.synthetic not importable yet: {exc}")
    kwargs: dict[str, Any] = {}
    params = inspect.signature(builder).parameters
    for name in params:
        candidate = None
        for attr in ("Synthetic" + name.capitalize(), "Synthetic" + name.title().replace("_", "")):
            candidate = getattr(synthetic, attr, None)
            if candidate is not None:
                break
        if candidate is None:
            factory = getattr(synthetic, f"synthetic_{name}", None)
            if factory is not None:
                candidate = factory
        if candidate is None:
            if params[name].default is not inspect.Parameter.empty:
                continue
            pytest.skip(f"no synthetic implementation found for build_registry({name}=...)")
        try:
            kwargs[name] = (
                candidate() if inspect.isclass(candidate) or callable(candidate) else candidate
            )
        except TypeError:
            kwargs[name] = candidate
    return builder(**kwargs)


def _specs(registry: Any) -> list[Any]:
    if hasattr(registry, "all"):
        return list(registry.all())
    if hasattr(registry, "_tools"):
        return list(registry._tools.values())
    pytest.skip("registry exposes neither all() nor _tools")


def test_no_tool_mutates_state() -> None:
    registry = _build_registry()
    offenders = []
    for spec in _specs(registry):
        name = str(spec.name)
        if getattr(spec, "mutating", False):
            offenders.append(name)
        if any(name.startswith(verb) or f"_{verb}" in name for verb in _MUTATING_VERBS):
            offenders.append(name)
    assert not offenders, f"mutating tools are forbidden (ADR-0010): {offenders}"


def test_no_tool_schema_accepts_client_id() -> None:
    registry = _build_registry()
    offenders = []
    for spec in _specs(registry):
        schema = spec.args_schema.model_json_schema()
        if "client_id" in schema.get("properties", {}):
            offenders.append(spec.name)
    assert not offenders, f"client_id must be injected, never model-supplied: {offenders}"


def test_every_tool_is_reachable_from_at_most_documented_intents() -> None:
    registry = _build_registry()
    try:
        from actinver_agent.tools.registry import INTENT_TOOL_MAP
    except ImportError:
        pytest.skip("INTENT_TOOL_MAP not present yet")
    reachable = {name for names in INTENT_TOOL_MAP.values() for name in names}
    unknown = reachable - {spec.name for spec in _specs(registry)}
    assert not unknown, f"INTENT_TOOL_MAP references unregistered tools: {unknown}"
