"""Graph assembly (docs/01-architecture/06 §2).

The topology is the compliance control. Mandatory steps are edges, not tools:
the model cannot route around ``suitability_gate``, ``compliance_guard`` or
``audit_sink`` because they are not things it can choose. Every node is wrapped
so the write-once identity fields can never change mid-run.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from actinver_agent.deps import Dependencies
from actinver_agent.graph.nodes import composer, guards, routing, suitability_node
from actinver_agent.graph.nodes.agent_core import agent_core, plan, tool_execution
from actinver_agent.graph.nodes.audit import audit_sink
from actinver_agent.graph.nodes.transaction import (
    await_form_submission,
    execute_transaction,
    transaction_planner,
)
from actinver_agent.graph.state import (
    ADVISORY_INTENTS,
    TRANSACTIONAL_INTENTS,
    AdvisorState,
    GuardrailAction,
    assert_identity_unchanged,
)

Node = Any  # a LangGraph node callable; kept loose so add_node overloads resolve

NODE_NAMES: tuple[str, ...] = (
    "ingress_guard",
    "intent_router",
    "entitlement_gate",
    "plan",
    "tool_execution",
    "agent_core",
    "suitability_gate",
    "transaction_planner",
    "compliance_guard",
    "response_composer",
    "audit_sink",
    "await_form_submission",
    "execute_transaction",
)


def guarded(node: Callable[..., Awaitable[dict[str, Any]]], deps: Dependencies | None) -> Node:
    """Invariant 1: identity fields are write-once at graph entry."""

    async def _run(state: AdvisorState) -> dict[str, Any]:
        update = await node(state, deps) if deps is not None else await node(state)
        if update:
            assert_identity_unchanged(state, update)  # type: ignore[arg-type]
        return update

    _run.__name__ = getattr(node, "__name__", "node")
    return _run


def build_graph(deps: Dependencies, checkpointer: Any) -> Any:
    graph: Any = StateGraph(AdvisorState)

    graph.add_node("ingress_guard", guarded(guards.ingress_guard, deps))
    graph.add_node("intent_router", guarded(routing.intent_router, deps))
    graph.add_node("entitlement_gate", guarded(routing.entitlement_gate, deps))
    graph.add_node("plan", guarded(plan, deps))
    graph.add_node("tool_execution", guarded(tool_execution, deps))
    graph.add_node("agent_core", guarded(agent_core, deps))
    graph.add_node("suitability_gate", guarded(suitability_node.suitability_gate, deps))
    graph.add_node("transaction_planner", guarded(transaction_planner, deps))
    graph.add_node("compliance_guard", guarded(guards.compliance_guard, deps))
    graph.add_node("response_composer", guarded(composer.response_composer, deps))
    graph.add_node("audit_sink", guarded(audit_sink, deps))
    graph.add_node("await_form_submission", guarded(await_form_submission, None))
    graph.add_node("execute_transaction", guarded(execute_transaction, deps))

    graph.add_edge(START, "ingress_guard")
    graph.add_conditional_edges(
        "ingress_guard",
        after_ingress,
        {"router": "intent_router", "refuse": "response_composer"},
    )
    graph.add_conditional_edges(
        "intent_router",
        after_router,
        {"gate": "entitlement_gate", "refuse": "response_composer"},
    )
    graph.add_conditional_edges(
        "entitlement_gate",
        after_entitlement,
        {"plan": "plan", "refuse": "response_composer"},
    )
    graph.add_edge("plan", "tool_execution")
    graph.add_conditional_edges(
        "tool_execution",
        after_tools,
        {"more_tools": "tool_execution", "generate": "agent_core"},
    )
    graph.add_conditional_edges(
        "agent_core",
        after_agent_core,
        {
            "suitability": "suitability_gate",
            "transaction": "transaction_planner",
            "guard": "compliance_guard",
            "refuse": "response_composer",
        },
    )
    graph.add_conditional_edges(
        "suitability_gate",
        after_suitability,
        {"guard": "compliance_guard", "refuse": "response_composer"},
    )
    graph.add_conditional_edges(
        "transaction_planner",
        after_planner,
        {"guard": "compliance_guard", "refuse": "response_composer"},
    )
    graph.add_conditional_edges(
        "compliance_guard",
        after_compliance,
        {"rewrite": "agent_core", "compose": "response_composer", "refuse": "response_composer"},
    )
    graph.add_edge("response_composer", "audit_sink")
    graph.add_conditional_edges(
        "audit_sink",
        after_audit,
        {"await_form": "await_form_submission", "end": END},
    )
    graph.add_conditional_edges(
        "await_form_submission",
        after_await,
        {"execute": "execute_transaction", "end": END},
    )
    graph.add_edge("execute_transaction", "audit_sink")

    return graph.compile(checkpointer=checkpointer)


# ── Edge predicates ───────────────────────────────────────────────────────────


def after_ingress(state: AdvisorState) -> Literal["router", "refuse"]:
    verdict = state.get("guardrail_input")
    if verdict is None or verdict.action is GuardrailAction.BLOCK or state.get("error"):
        return "refuse"
    return "router"


def after_router(state: AdvisorState) -> Literal["gate", "refuse"]:
    return "refuse" if state.get("error") else "gate"


def after_entitlement(state: AdvisorState) -> Literal["plan", "refuse"]:
    return "refuse" if state.get("error") else "plan"


def after_tools(state: AdvisorState) -> Literal["more_tools", "generate"]:
    return "more_tools" if state.get("needs_more_tools") else "generate"


def after_agent_core(
    state: AdvisorState,
) -> Literal["suitability", "transaction", "guard", "refuse"]:
    if state.get("error"):
        return "refuse"
    intent = state.get("intent")
    if intent in ADVISORY_INTENTS and state.get("suitability") is None:
        return "suitability"
    if intent in TRANSACTIONAL_INTENTS and state.get("form_spec") is None:
        return "transaction"
    return "guard"


def after_suitability(state: AdvisorState) -> Literal["guard", "refuse"]:
    return "refuse" if state.get("error") else "guard"


def after_planner(state: AdvisorState) -> Literal["guard", "refuse"]:
    return "refuse" if state.get("error") else "guard"


def after_compliance(state: AdvisorState) -> Literal["rewrite", "compose", "refuse"]:
    if state.get("error"):
        return "refuse"
    verdict = state.get("guardrail_output")
    if verdict is None:
        return "refuse"
    if verdict.action is GuardrailAction.REWRITE:
        return "rewrite"
    if verdict.action is GuardrailAction.BLOCK:
        return "refuse"
    return "compose"


def after_audit(state: AdvisorState) -> Literal["await_form", "end"]:
    if state.get("form_spec") is not None and not state.get("receipt") and not state.get("error"):
        return "await_form"
    return "end"


def after_await(state: AdvisorState) -> Literal["execute", "end"]:
    return "execute" if state.get("receipt") else "end"


# ── Topology inspection (for the build-time assertions) ───────────────────────


def graph_edges(compiled: Any) -> set[tuple[str, str]]:
    """Every edge of the compiled graph, conditional targets included."""
    drawable = compiled.get_graph()
    return {(e.source, e.target) for e in drawable.edges}


def paths_between(edges: set[tuple[str, str]], source: str, target: str) -> list[list[str]]:
    """All simple paths source → target (the graph is small)."""
    adjacency: dict[str, list[str]] = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
    out: list[list[str]] = []

    def walk(node: str, path: list[str]) -> None:
        if node == target:
            out.append(path)
            return
        for nxt in adjacency.get(node, []):
            if nxt not in path:
                walk(nxt, [*path, nxt])

    walk(source, [source])
    return out
