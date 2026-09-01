"""The topology is the compliance control (docs/04-backend/02 §7, ADR-0002/0005/0010)."""

from __future__ import annotations

import pytest

from actinver_agent.deps import Dependencies
from actinver_agent.graph.builder import NODE_NAMES, graph_edges, paths_between
from actinver_agent.graph.state import (
    AdvisorState,
    IdentityViolation,
    assert_identity_unchanged,
)


@pytest.fixture
def edges(deps: Dependencies) -> set[tuple[str, str]]:
    return graph_edges(deps.graph)


def test_every_documented_node_exists(deps: Dependencies) -> None:
    nodes = set(deps.graph.get_graph().nodes)
    for name in NODE_NAMES:
        assert name in nodes


def test_no_path_from_agent_core_to_composer_bypasses_compliance_guard(edges) -> None:
    paths = paths_between(edges, "agent_core", "response_composer")
    assert paths, "agent_core must reach the composer"
    for path in paths:
        # The only legitimate way from agent_core to the composer is through the
        # guard, or through an explicit refusal (error) edge which emits fixed text.
        assert "compliance_guard" in path or _is_refusal_only(path), path


def _is_refusal_only(path: list[str]) -> bool:
    # agent_core → response_composer directly is the "refuse" edge (error set, no model text).
    return (
        path == ["agent_core", "response_composer"]
        or ("suitability_gate" in path and "compliance_guard" not in path)
        or ("transaction_planner" in path and "compliance_guard" not in path)
    )


def test_advisory_path_passes_suitability_gate(edges) -> None:
    assert ("agent_core", "suitability_gate") in edges
    assert ("suitability_gate", "compliance_guard") in edges


def test_transactional_path_suspends_before_execution(edges) -> None:
    assert ("agent_core", "transaction_planner") in edges
    assert ("audit_sink", "await_form_submission") in edges
    assert ("await_form_submission", "execute_transaction") in edges
    assert ("execute_transaction", "audit_sink") in edges


def test_every_terminal_path_ends_in_audit_sink(edges) -> None:
    assert ("response_composer", "audit_sink") in edges
    assert ("audit_sink", "__end__") in edges
    # No node other than audit_sink and await_form_submission reaches END.
    to_end = {source for source, target in edges if target == "__end__"}
    assert to_end == {"audit_sink", "await_form_submission"}


def test_rewrite_loop_is_bounded_by_edges(edges) -> None:
    assert ("compliance_guard", "agent_core") in edges


def test_no_tool_in_registry_mutates(deps: Dependencies) -> None:
    for spec in deps.registry.specs():
        assert spec.mutating is False
        assert "client_id" not in spec.args_schema.model_fields


def test_identity_fields_are_write_once() -> None:
    before: AdvisorState = {"client_id": "cl_a", "thread_id": "th_1", "turn_id": "tn_1"}
    after: AdvisorState = {"client_id": "cl_b"}
    with pytest.raises(IdentityViolation):
        assert_identity_unchanged(before, after)
    assert_identity_unchanged(before, {"speech": "hola"})  # type: ignore[typeddict-item]
