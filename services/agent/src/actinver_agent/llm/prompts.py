"""Prompt library.

Prompts are versioned files under ``prompts/``, not string literals in code
(docs/01-architecture/06 §4). Every evidence record cites the prompt version.
Disclosure texts are legal-approved and inserted verbatim; the model may not
paraphrase them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from actinver_agent.graph.state import AdvisorState, Intent

_VERSION_RE = re.compile(r"<!--\s*version:\s*(?P<version>[^\s]+)\s*-->")
_TASK_FILES: dict[Intent, str] = {
    Intent.PORTFOLIO_INSPECT: "portfolio_inspect.md",
    Intent.PORTFOLIO_EXPLAIN: "explain_performance.md",
    Intent.MARKET_CONTEXT: "market_context.md",
    Intent.PRODUCT_DISCOVER: "product_discovery.md",
    Intent.ADVISORY_RECOMMEND: "product_discovery.md",
    Intent.SIMULATE: "simulate.md",
    Intent.TRANSACT_BUY: "transaction_draft.md",
    Intent.TRANSACT_SELL: "transaction_draft.md",
    Intent.TRANSACT_SWITCH: "transaction_draft.md",
    Intent.TRANSACT_REDEEM: "transaction_draft.md",
    Intent.ACCOUNT_ADMIN: "account_admin.md",
    Intent.PROFILE_UPDATE: "account_admin.md",
}

DEGRADATION_NOTICE_ES = (
    "NOTA: este cliente NO tiene contratado el servicio asesorado. Puedes describir "
    "productos de forma general, pero NO puedes recomendar uno para su situación "
    'particular ni decir que "le conviene". Ofrece contactar a su asesor.'
)


@dataclass(frozen=True, slots=True)
class Disclosure:
    id: str
    text: str
    version: str


class PromptLibrary:
    def __init__(self, prompts_dir: str | Path) -> None:
        self._dir = Path(prompts_dir)
        self._system = self._read("system/advisor.es-MX.md")
        self._boundaries = self._read("system/boundaries.es-MX.md")
        self._disclosures_raw = self._read("system/disclosures.es-MX.md")
        self._router = self._read("router/intent.md")
        self._lexicon: dict[str, Any] = (
            yaml.safe_load(self._read("system/lexicon.es-MX.yaml")) or {}
        )
        self._tasks: dict[str, str] = {
            path.name: path.read_text(encoding="utf-8")
            for path in (self._dir / "task").glob("*.md")
        }
        self.version = _version_of(self._system, default="advisor-es-MX@unversioned")
        self.disclosures_version = _version_of(
            self._disclosures_raw, default="disclosures-es-MX@unversioned"
        )
        self.disclosures: dict[str, Disclosure] = _parse_disclosures(
            self._disclosures_raw, self.disclosures_version
        )

    def _read(self, relative: str) -> str:
        return (self._dir / relative).read_text(encoding="utf-8")

    @property
    def router_prompt(self) -> str:
        return self._router

    @property
    def lexicon(self) -> dict[str, Any]:
        return self._lexicon

    def task_prompt(self, intent: Intent | str) -> str:
        try:
            key = Intent(str(intent))
        except ValueError:
            return ""
        filename = _TASK_FILES.get(key)
        return self._tasks.get(filename, "") if filename else ""

    def render_system(
        self,
        state: AdvisorState,
        *,
        tool_declarations: list[dict[str, Any]],
        degradation_notice: str | None = None,
    ) -> str:
        """Fill the system prompt skeleton. Only the first name and profile bands
        reach the model (docs/01-architecture/04 §6)."""
        profile = state.get("investor_profile")
        entitlements = state.get("entitlements")
        services: list[str] = []
        if entitlements is not None:
            if entitlements.contracted_for_advised_services:
                services.append("asesoría de inversiones")
            if entitlements.contracted_for_execution:
                services.append("ejecución de operaciones")
        if not services:
            services.append("información (no asesorado)")

        declarations = (
            "\n".join(f"- {d['name']}: {d['description']}" for d in tool_declarations)
            or "- (sin herramientas para esta intención)"
        )

        replacements = {
            "{tool_declarations}": declarations,
            "{first_name}": state.get("first_name") or "cliente",
            "{risk_category}": str(profile.risk_category) if profile else "no disponible",
            "{horizon_band}": profile.horizon_band if profile else "no disponible",
            "{knowledge_level}": str(profile.knowledge_level) if profile else "no disponible",
            "{service_types}": ", ".join(services),
            "{degradation_notice}": degradation_notice or "",
        }
        rendered = self._system
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        register = state.get("register", "tu")
        register_line = (
            'Trato de "usted" durante toda la conversación.' if register == "usted" else ""
        )
        return "\n\n".join(part for part in (rendered, self._boundaries, register_line) if part)


def _version_of(text: str, *, default: str) -> str:
    match = _VERSION_RE.search(text)
    return match.group("version") if match else default


def _parse_disclosures(text: str, version: str) -> dict[str, Disclosure]:
    """``## ID`` headings followed by the verbatim legal text."""
    out: dict[str, Disclosure] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                out[current] = Disclosure(current, " ".join(buffer).strip(), version)
            current = line[3:].strip()
            buffer = []
        elif current is not None and not line.startswith("<!--"):
            if line.strip():
                buffer.append(line.strip())
    if current is not None:
        out[current] = Disclosure(current, " ".join(buffer).strip(), version)
    return out
