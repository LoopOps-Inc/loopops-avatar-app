"""GuardrailPort implemented as a library in this process."""

from __future__ import annotations

from actinver_agent.graph.state import GuardrailVerdict
from actinver_agent.guardrails.disclosures import DisclosureCatalogue, load_disclosures
from actinver_agent.guardrails.engine import GuardrailEngine
from actinver_agent.ports import OutputCheckRequest


class InProcessGuardrail:
    def __init__(
        self,
        disclosures: DisclosureCatalogue | None = None,
        *,
        prompts_dir: str = "prompts",
        min_confidence: float = 0.60,
    ) -> None:
        self._catalogue = disclosures or load_disclosures(prompts_dir)
        self._engine = GuardrailEngine(self._catalogue)
        self._min_confidence = min_confidence

    @property
    def engine(self) -> GuardrailEngine:
        return self._engine

    async def check_input(
        self, *, text: str, transcript_confidence: float | None
    ) -> tuple[GuardrailVerdict, str]:
        result = self._engine.check_input(
            text, transcript_confidence=transcript_confidence, min_confidence=self._min_confidence
        )
        return result.verdict, result.redacted_text

    async def scan_retrieved(self, *, text: str) -> bool:
        return self._engine.scan_retrieved(text)

    async def check_output(self, request: OutputCheckRequest) -> GuardrailVerdict:
        return self._engine.check_output(request)

    async def disclosure_texts(self, ids: list[str]) -> dict[str, tuple[str, str]]:
        return self._catalogue.texts(ids)

    async def health(self) -> bool:
        return True
