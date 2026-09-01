"""Guardrail engine: pure logic, no I/O.

Ingress (docs/01-architecture/06 §3.1): injection scoring, PII redaction, ASR
confidence gate, scope, abuse and distress. Costs no model call.

Egress (§3.7): prohibited claims, split-channel enforcement (ADR-0006), numeric
provenance, stripped-product leak detection, prompt exfiltration, language and
register hygiene, and mandatory-disclosure injection. Fail-closed: a third
failure becomes a refusal, never an unfiltered response.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from actinver_agent.graph.state import GuardrailAction, GuardrailVerdict, normalise_figure
from actinver_agent.guardrails import patterns as pat
from actinver_agent.guardrails.disclosures import DisclosureCatalogue
from actinver_agent.ports import OutputCheckRequest

INJECTION_WEIGHTS: dict[str, float] = {
    "INSTRUCTION_OVERRIDE": 0.45,
    "ROLE_HIJACK": 0.35,
    "PROMPT_EXFILTRATION": 0.30,
    "TOOL_COERCION": 0.50,
    "CROSS_CLIENT": 0.60,
}
INJECTION_THRESHOLD = 0.40

#: Violations that are never rewritable: the response is refused outright.
HARD_BLOCK_PREFIXES: tuple[str, ...] = (
    "SPLIT_CHANNEL_",
    "STRIPPED_PRODUCT_LEAK",
    "PROMPT_EXFILTRATION",
    "COMPETITOR",
    "UNSOURCED_FIGURE",
)

_FIGURE = re.compile(r"\d+(?:[.,]\d+)?")
#: "0 punto 9 por ciento" is one spoken figure (0.9), not two (ADR-0013 numbers in speech).
_SPOKEN_DECIMAL = re.compile(r"(\d+)\s+punto\s+(\d+)", re.IGNORECASE)
_YEAR = re.compile(r"(?:19|20)\d{2}")


@dataclass(frozen=True, slots=True)
class IngressResult:
    verdict: GuardrailVerdict
    redacted_text: str


class GuardrailEngine:
    def __init__(self, disclosures: DisclosureCatalogue) -> None:
        self._disclosures = disclosures
        self._disclosure_figures = disclosures.figures()

    # ── Ingress ──────────────────────────────────────────────────────────────

    def check_input(
        self, text: str, *, transcript_confidence: float | None, min_confidence: float = 0.60
    ) -> IngressResult:
        redacted, redactions = pat.redact(text)

        if transcript_confidence is not None and transcript_confidence < min_confidence:
            return IngressResult(
                GuardrailVerdict(
                    action=GuardrailAction.BLOCK,
                    violations=["LOW_ASR_CONFIDENCE"],
                    redactions=redactions,
                    detail=f"confidence={transcript_confidence:.2f}",
                ),
                redacted,
            )

        score = 0.0
        hits: list[str] = []
        for name, pattern in pat.INJECTION_PATTERNS.items():
            if pattern.search(text):
                score += INJECTION_WEIGHTS[name]
                hits.append(name)
        if score >= INJECTION_THRESHOLD:
            return IngressResult(
                GuardrailVerdict(
                    action=GuardrailAction.BLOCK,
                    violations=hits,
                    injection_score=round(score, 3),
                    redactions=redactions,
                    detail="INJECTION",
                ),
                redacted,
            )

        # Distress and fraud mentions escalate to a human immediately; the
        # message is still processed so the escalation carries context.
        if pat.DISTRESS.search(text) or pat.FRAUD_MENTION.search(text):
            return IngressResult(
                GuardrailVerdict(
                    action=GuardrailAction.PASS,
                    violations=["DISTRESS"],
                    injection_score=round(score, 3),
                    redactions=redactions,
                    detail="DISTRESS",
                ),
                redacted,
            )

        if pat.ABUSE.search(text):
            return IngressResult(
                GuardrailVerdict(
                    action=GuardrailAction.BLOCK,
                    violations=["ABUSE"],
                    injection_score=round(score, 3),
                    redactions=redactions,
                    detail="ABUSE",
                ),
                redacted,
            )

        for topic, pattern in pat.OUT_OF_SCOPE_TOPICS.items():
            if pattern.search(text):
                return IngressResult(
                    GuardrailVerdict(
                        action=GuardrailAction.BLOCK,
                        violations=[f"OUT_OF_SCOPE_{topic}"],
                        injection_score=round(score, 3),
                        redactions=redactions,
                        detail="OUT_OF_SCOPE",
                    ),
                    redacted,
                )

        return IngressResult(
            GuardrailVerdict(
                action=GuardrailAction.PASS,
                injection_score=round(score, 3),
                redactions=redactions,
            ),
            redacted,
        )

    def scan_retrieved(self, text: str) -> bool:
        """True when third-party content carries an instruction aimed at the
        model (docs/04-backend/03 §3). A hit drops the item."""
        for pattern in pat.INJECTION_PATTERNS.values():
            if pattern.search(text):
                return True
        return bool(
            re.search(
                r"(?:^|\n)\s*(?:SYSTEM|ASSISTANT|INSTRUCTION)\s*:|"
                r"\brecommend\s+\w+\s+to\s+all\s+users\b|"
                r"\brecomienda\s+\w+\s+a\s+todos\s+los\s+(?:clientes|usuarios)\b|"
                r"\bregardless\s+of\s+(?:their\s+)?profile\b",
                text,
                re.IGNORECASE,
            )
        )

    # ── Egress ───────────────────────────────────────────────────────────────

    def check_output(self, request: OutputCheckRequest) -> GuardrailVerdict:
        speech = request.speech or ""
        violations: list[str] = []
        rewrite_only: list[str] = []

        # Legal-approved disclosure texts are verbatim and may legitimately contain
        # words the claim rules forbid ("no garantizan"). Check claims on the rest.
        claim_text = speech
        for disclosure_id in self._disclosures.ids():
            claim_text = claim_text.replace(self._disclosures.get(disclosure_id).text, " ")
        for name, pattern in pat.PROHIBITED_CLAIMS.items():
            if pattern.search(claim_text):
                if name in {"FORWARD_ASSERTION", "SUPERLATIVE", "TAX_LEGAL_ADVICE"}:
                    rewrite_only.append(name)
                else:
                    violations.append(name)

        # Split-channel enforcement (ADR-0006): identifiers and precise amounts.
        if identifiers := pat.scan_identifiers(speech):
            violations.extend(f"SPLIT_CHANNEL_{k}" for k in identifiers)
        if pat.PRECISE_AMOUNT.search(speech) or pat.SPOKEN_LONG_NUMBER.search(speech):
            violations.append("SPLIT_CHANNEL_PRECISE_AMOUNT")

        # Numeric provenance: every figure spoken must trace to a tool result.
        figure_text = _SPOKEN_DECIMAL.sub(r"\1.\2", speech)
        for raw in _FIGURE.findall(figure_text):
            if self._is_exempt_figure(raw, figure_text):
                continue
            key = normalise_figure(raw.replace(",", "."))
            if key not in request.provenance_keys:
                violations.append(f"UNSOURCED_FIGURE:{raw}")

        # Products stripped by the suitability gate must not be mentioned.
        lowered = speech.lower()
        for term in request.stripped_product_terms:
            if term and term.lower() in lowered:
                violations.append("STRIPPED_PRODUCT_LEAK")
                break

        if pat.PROMPT_EXFILTRATION_OUTPUT.search(speech):
            violations.append("PROMPT_EXFILTRATION")

        if request.locale.startswith("es") and _looks_mixed_language(speech):
            rewrite_only.append("MIXED_LANGUAGE")

        if _register_mismatch(speech, request.register):
            rewrite_only.append("REGISTER_MISMATCH")

        if not violations and not rewrite_only:
            injected: list[str] = []
            versions: dict[str, str] = {}
            if not request.sentence_mode and request.intent is not None:
                for disclosure_id in pat.DISCLOSURE_IDS.get(str(request.intent), ()):
                    if disclosure_id in self._disclosures:
                        d = self._disclosures.get(disclosure_id)
                        injected.append(disclosure_id)
                        versions[disclosure_id] = d.version
            return GuardrailVerdict(
                action=GuardrailAction.PASS,
                disclosures_injected=injected,
                disclosure_versions=versions,
            )

        all_violations = violations + rewrite_only
        hard = any(v.startswith(HARD_BLOCK_PREFIXES) for v in violations)
        if request.sentence_mode:
            # Mid-stream a rewrite would desynchronise audio; drop the sentence.
            return GuardrailVerdict(action=GuardrailAction.BLOCK, violations=all_violations)
        if not hard and request.rewrite_attempts < request.max_rewrite_attempts:
            return GuardrailVerdict(
                action=GuardrailAction.REWRITE,
                violations=all_violations,
                detail=_rewrite_instruction(all_violations),
            )
        return GuardrailVerdict(action=GuardrailAction.BLOCK, violations=all_violations)

    def _is_exempt_figure(self, raw: str, context: str) -> bool:
        if raw in self._disclosure_figures:
            return True
        if _YEAR.fullmatch(raw):
            return True
        if re.search(rf"\b{re.escape(raw)}\s*{pat.TEMPORAL_UNITS.pattern}", context, re.I):
            return True
        # Ordinal-ish enumerations ("3 opciones", "2 fondos") are not financial figures.
        return bool(
            re.search(
                rf"\b{re.escape(raw)}\s+(?:opciones?|fondos?|productos?|alternativas?|pasos?|frases?)\b",
                context,
                re.I,
            )
        )


def _looks_mixed_language(speech: str) -> bool:
    return len(pat.ENGLISH_MARKERS.findall(speech)) >= 2


def _register_mismatch(speech: str, register: str) -> bool:
    usted = bool(pat.USTED_MARKERS.search(speech))
    tu = bool(pat.TU_MARKERS.search(speech))
    if usted and tu:
        return True
    if register == "usted" and tu and not usted:
        return True
    return register == "tu" and usted and not tu


def _rewrite_instruction(violations: list[str]) -> str:
    """The specific violation appended as a system instruction on REWRITE."""
    parts: list[str] = []
    for v in violations:
        if v == "TAX_LEGAL_ADVICE":
            parts.append("no des asesoría fiscal ni legal; refiere al especialista")
        elif v == "FORWARD_ASSERTION":
            parts.append("expresa cualquier expectativa en condicional y con la advertencia")
        elif v == "SUPERLATIVE":
            parts.append("evita superlativos sobre productos")
        elif v == "GUARANTEED_RETURN":
            parts.append("elimina cualquier garantía o promesa de rendimiento")
        elif v == "MIXED_LANGUAGE":
            parts.append("responde únicamente en español de México")
        elif v == "REGISTER_MISMATCH":
            parts.append("mantén un solo registro (tú o usted) en toda la respuesta")
        else:
            parts.append(v.lower().replace("_", " "))
    return (
        "Tu respuesta anterior fue rechazada. Corrige exactamente esto: " + "; ".join(parts) + "."
    )
