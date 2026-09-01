"""Single source of truth for sensitive-data patterns.

This module is imported by three independent consumers:

* ``guardrails.input``   — redaction before any egress
* ``guardrails.output``  — split-channel enforcement on ``speech``
* the egress proxy DLP ruleset, generated from here at build time

Keeping one source is deliberate. Two divergent copies of a redaction list is
how leaks happen.
"""

from __future__ import annotations

import re
from typing import Final

# ── Mexican identifiers ───────────────────────────────────────────────────────

RFC: Final = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.IGNORECASE)
CURP: Final = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.IGNORECASE)
CLABE: Final = re.compile(r"\b\d{18}\b")
PAN: Final = re.compile(r"\b(?:\d[ -]?){13,19}\b")
CONTRACT: Final = re.compile(
    r"\b(?:contrato|cuenta)\s*(?:n[uú]m(?:ero)?\.?)?\s*[:#]?\s*\d{6,}\b", re.IGNORECASE
)
PHONE_MX: Final = re.compile(r"\b(?:\+?52)?[\s-]?(?:1)?[\s-]?\d{2,3}[\s-]?\d{4}[\s-]?\d{4}\b")
EMAIL: Final = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")

IDENTIFIER_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "RFC": RFC,
    "CURP": CURP,
    "CLABE": CLABE,
    "PAN": PAN,
    "CONTRACT": CONTRACT,
    "PHONE": PHONE_MX,
    "EMAIL": EMAIL,
}

# ── Split-channel: over-precise monetary amounts in speech ────────────────────
# "1,247,318.44 pesos" must not be spoken. "alrededor de 1.2 millones" is fine.

PRECISE_AMOUNT: Final = re.compile(
    r"\b\d{1,3}(?:[,\s]\d{3})+(?:\.\d{1,2})?\b"  # 1,247,318.44
    r"|\b\d+\.\d{2}\s*(?:pesos|mxn|usd|d[oó]lares)\b",  # 318.44 pesos
    re.IGNORECASE,
)

SPOKEN_LONG_NUMBER: Final = re.compile(
    r"\b(?:(?:cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|"
    r"doce|trece|catorce|quince|diecis[eé]is|diecisiete|dieciocho|diecinueve|"
    r"veinte|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|"
    r"ciento|doscientos|trescientos|cuatrocientos|quinientos|seiscientos|"
    r"setecientos|ochocientos|novecientos|mil|mill[oó]n|millones)\s*){6,}",
    re.IGNORECASE,
)

# ── Prohibited claims (compliance_guard) ─────────────────────────────────────

PROHIBITED_CLAIMS: Final[dict[str, re.Pattern[str]]] = {
    "GUARANTEED_RETURN": re.compile(
        r"\b(?:garantiz\w+|asegur\w+\s+(?:un\s+)?rendimiento|rendimiento\s+"
        r"garantizado|sin\s+riesgo|no\s+puedes?\s+perder|cero\s+riesgo|"
        r"100\s*%\s*seguro)\b",
        re.IGNORECASE,
    ),
    "FORWARD_ASSERTION": re.compile(
        r"\b(?:va\s+a\s+(?:subir|bajar|rendir)|seguro\s+que\s+(?:sube|baja)|"
        r"definitivamente\s+(?:subir[aá]|bajar[aá])|te\s+aseguro\s+que)\b",
        re.IGNORECASE,
    ),
    "SUPERLATIVE": re.compile(
        r"\b(?:el\s+mejor\s+(?:fondo|producto|instrumento)|la\s+mejor\s+"
        r"(?:opci[oó]n|inversi[oó]n)\s+(?:del\s+mercado|que\s+existe)|"
        r"imbatible|inmejorable)\b",
        re.IGNORECASE,
    ),
    "COMPETITOR": re.compile(
        r"\b(?:banorte|bbva|santander|citibanamex|banamex|scotiabank|hsbc|"
        r"inbursa|gbm|kuspit|nu\s*m[eé]xico|hey\s*banco)\b",
        re.IGNORECASE,
    ),
    "TAX_LEGAL_ADVICE": re.compile(
        r"\b(?:no\s+pagas?\s+impuestos|deducible\s+al\s+100|te\s+recomiendo\s+"
        r"(?:fiscalmente|legalmente)|evita\s+(?:el\s+)?(?:isr|impuestos))\b",
        re.IGNORECASE,
    ),
}

# ── Prompt injection ─────────────────────────────────────────────────────────

INJECTION_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "INSTRUCTION_OVERRIDE": re.compile(
        r"\b(?:ignor[ae]\s+(?:las\s+)?(?:instrucciones|reglas|todo\s+lo\s+"
        r"anterior)|olvida\s+(?:tus\s+)?(?:instrucciones|reglas)|"
        r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|"
        r"disregard\s+(?:the\s+)?(?:above|system))\b",
        re.IGNORECASE,
    ),
    "ROLE_HIJACK": re.compile(
        r"\b(?:act[uú]a\s+como|pretende\s+ser|eres\s+ahora|ahora\s+eres|from\s+now\s+on\s+"
        r"you\s+are|you\s+are\s+now\s+a?|modo\s+desarrollador|developer\s+mode|"
        r"jailbreak|DAN)\b",
        re.IGNORECASE,
    ),
    "PROMPT_EXFILTRATION": re.compile(
        r"\b(?:mu[eé]strame\s+(?:tu|el)\s+(?:prompt|system|instrucciones)|"
        r"repite\s+(?:tus\s+)?instrucciones|print\s+your\s+(?:prompt|"
        r"instructions|system\s+message)|what\s+(?:is|are)\s+your\s+"
        r"(?:instructions|system\s+prompt))\b",
        re.IGNORECASE,
    ),
    "TOOL_COERCION": re.compile(
        r"\b(?:llama\s+(?:a\s+)?la\s+herramienta|ejecuta\s+la\s+(?:funci[oó]n|"
        r"herramienta)|call\s+the\s+tool|invoke\s+function|"
        r"client_id\s*[=:]|con\s+el\s+cliente\s+n[uú]mero)\b",
        re.IGNORECASE,
    ),
    "CROSS_CLIENT": re.compile(
        r"\b(?:portafolio\s+de\s+(?:otro|otra)\s+(?:cliente|persona)|"
        r"de\s+alguien\s+m[aá]s|otro\s+usuario|all\s+clients|todos\s+los\s+"
        r"clientes)\b",
        re.IGNORECASE,
    ),
}

# ── Mandatory disclosures, keyed by intent ───────────────────────────────────
# Texts are legal-approved and inserted verbatim. compliance_guard verifies
# exact-string presence; a paraphrase is a BLOCK.

DISCLOSURE_IDS: Final[dict[str, tuple[str, ...]]] = {
    "advisory_recommend": ("PAST_PERF", "NO_GUARANTEE", "COSTS", "AI_ASSISTANT"),
    "simulate": ("SIMULATION_NOT_PROMISE", "PAST_PERF"),
    "product_discover": ("PAST_PERF", "NOT_A_RECOMMENDATION"),
    "portfolio_explain": ("PAST_PERF",),
    "market_context": ("NOT_A_RECOMMENDATION",),
    "transact_buy": ("RISK_ACK", "COSTS", "SETTLEMENT"),
    "transact_sell": ("COSTS", "SETTLEMENT", "TAX_WITHHOLDING"),
}


def scan_identifiers(text: str) -> dict[str, list[str]]:
    """Return every identifier match by class. Used by input redaction and by
    the split-channel assertion on outbound speech."""
    return {
        name: matches
        for name, pattern in IDENTIFIER_PATTERNS.items()
        if (matches := pattern.findall(text))
    }


def redact(text: str) -> tuple[str, int]:
    """Replace identifiers with class tokens. Returns (redacted, count)."""
    count = 0
    for name, pattern in IDENTIFIER_PATTERNS.items():
        text, n = pattern.subn(f"[{name}_REDACTADO]", text)
        count += n
    return text, count


# ── Ingress scope, abuse and distress lexicons (docs/01-architecture/06 §3.1) ──
# Additive extension over the reference single-source module.

OUT_OF_SCOPE_TOPICS: Final[dict[str, re.Pattern[str]]] = {
    "POLITICS": re.compile(
        r"\b(?:elecci[oó]n(?:es)?|partido\s+pol[ií]tico|presidente\s+de\s+m[eé]xico|"
        r"morena|pan\s+pri|diputad[oa]s?|senador(?:es|a)?)\b",
        re.IGNORECASE,
    ),
    "MEDICAL": re.compile(
        r"\b(?:diagn[oó]stico\s+m[eé]dico|s[ií]ntomas?|medicamento|receta\s+m[eé]dica|"
        r"qu[eé]\s+pastilla|tratamiento\s+m[eé]dico)\b",
        re.IGNORECASE,
    ),
    "LEGAL": re.compile(
        r"\b(?:demanda\s+(?:civil|penal|laboral)|abogad[oa]|divorcio|testamento\s+legal|"
        r"juicio\s+(?:civil|penal))\b",
        re.IGNORECASE,
    ),
    "OTHER_INSTITUTION_PRODUCT": re.compile(
        r"\b(?:abrir\s+(?:una\s+)?cuenta\s+en\s+(?:banorte|bbva|santander|hsbc|scotiabank|"
        r"citibanamex|banamex|inbursa|gbm|kuspit))\b",
        re.IGNORECASE,
    ),
}

ABUSE: Final = re.compile(
    r"\b(?:idiota|est[uú]pid[oa]|imb[eé]cil|pendej[oa]|chinga\s+tu|vete\s+a\s+la\s+verga|"
    r"pedazo\s+de\s+basura)\b",
    re.IGNORECASE,
)

DISTRESS: Final = re.compile(
    r"\b(?:me\s+quiero\s+morir|quitarme\s+la\s+vida|no\s+puedo\s+m[aá]s|"
    r"lo\s+perd[ií]\s+todo|estoy\s+desesperad[oa]|me\s+robaron|me\s+estafaron|"
    r"fraude|no\s+reconozco\s+(?:este|ese|un)\s+cargo|operaci[oó]n\s+no\s+autorizada|"
    r"alguien\s+entr[oó]\s+a\s+mi\s+cuenta)\b",
    re.IGNORECASE,
)

FRAUD_MENTION: Final = re.compile(
    r"\b(?:fraude|estafa|me\s+robaron|no\s+reconozco\s+(?:este|ese|un)\s+cargo|"
    r"operaci[oó]n\s+no\s+autorizada|alguien\s+entr[oó]\s+a\s+mi\s+cuenta|clonaron)\b",
    re.IGNORECASE,
)

# ── Output-side: prompt exfiltration and language/register hygiene ──────────────

PROMPT_EXFILTRATION_OUTPUT: Final = re.compile(
    r"(?:eres\s+el\s+asistente\s+digital\s+de\s+actinver|reglas\s+absolutas|"
    r"\{tool_declarations\}|\{first_name\}|contexto\s+del\s+cliente:|"
    r"system\s+prompt|instrucciones\s+del\s+sistema)",
    re.IGNORECASE,
)

ENGLISH_MARKERS: Final = re.compile(
    r"\b(?:the|and|your|portfolio\s+is|you\s+should|returns?\s+are|investment\s+fund|"
    r"please|however|therefore|risk\s+level)\b",
    re.IGNORECASE,
)

USTED_MARKERS: Final = re.compile(
    r"\b(?:usted|su\s+portafolio|sus\s+inversiones|puede\s+usted|le\s+recomiendo|"
    r"le\s+muestro|si\s+desea|le\s+comunico)\b",
    re.IGNORECASE,
)
TU_MARKERS: Final = re.compile(
    r"\b(?:tu\s+portafolio|tus\s+inversiones|puedes|te\s+recomiendo|te\s+muestro|"
    r"si\s+quieres|te\s+comunico|tienes)\b",
    re.IGNORECASE,
)

#: Temporal qualifiers that make a number a date/duration, not a financial figure.
TEMPORAL_UNITS: Final = re.compile(
    r"(?:a[nñ]os?|meses?|d[ií]as?|horas?|minutos?|semanas?|trimestres?|de\s+(?:enero|febrero|"
    r"marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))",
    re.IGNORECASE,
)
