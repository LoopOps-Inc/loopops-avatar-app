"""SuitabilityPort implemented in-process (tests, single-binary dev).

In deployed environments the engine runs in suitability-service with a key the
agent cannot read; this class exists so the graph can be tested without HTTP.
"""

from __future__ import annotations

from actinver_agent.graph.state import InvestorProfile, ProductProfile, SuitabilityReport
from actinver_agent.ports import EvaluationInput
from actinver_agent.suitability.engine import SuitabilityEngine
from actinver_agent.suitability.rules import EvaluationContext


class InProcessSuitability:
    def __init__(self, engine: SuitabilityEngine) -> None:
        self._engine = engine

    @classmethod
    def with_key(cls, key: bytes, *, ruleset_version: int = 14) -> InProcessSuitability:
        return cls(SuitabilityEngine(ruleset_version, key))

    async def evaluate(
        self,
        *,
        client_id: str,  # noqa: ARG002 - part of the port; the engine is client-agnostic
        profile: InvestorProfile,
        products: list[ProductProfile],
        ctx: EvaluationInput,
    ) -> SuitabilityReport:
        return self._engine.evaluate(profile, products, EvaluationContext.from_input(ctx))

    async def verify(self, *, report: SuitabilityReport) -> bool:
        return self._engine.verify(report)

    async def health(self) -> bool:
        return True
