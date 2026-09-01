"""Disclosure texts are legal artefacts inserted verbatim (ADR-0013,
docs/05-security/05 §5, docs/07-data-governance/01 §6: "Exact-string test").

The expected strings below are the legal-approved texts from the reference
``prompts/system/disclosures.es-MX.md``. Changing one requires @legal review;
this test is the gate.
"""

from __future__ import annotations

import re
from pathlib import Path

EXPECTED: dict[str, str] = {
    "PAST_PERF": "Los rendimientos pasados no garantizan rendimientos futuros.",
    "NO_GUARANTEE": (
        "Esta información no constituye una garantía de resultados. El valor de tu "
        "inversión puede aumentar o disminuir."
    ),
    "COSTS": (
        "Consulta las comisiones aplicables en la ficha del producto y en la Guía de "
        "Servicios de Inversión."
    ),
    "AI_ASSISTANT": (
        "Soy un asistente automatizado de Actinver. Si prefieres, te comunico con tu asesor."
    ),
    "NOT_A_RECOMMENDATION": (
        "Esta información es de carácter general y no constituye una recomendación personalizada."
    ),
    "SIMULATION_NOT_PROMISE": (
        "Se trata de un escenario simulado con base en información histórica, no de una "
        "proyección garantizada."
    ),
    "RISK_ACK": (
        "Entiendo que el valor de esta inversión puede disminuir y que puedo recibir "
        "menos de lo que invertí."
    ),
    "SETTLEMENT": "La operación se liquida conforme a la fecha valor del producto.",
    "TAX_WITHHOLDING": (
        "La retención de ISR es estimada; el cálculo definitivo lo determina la "
        "institución conforme a la normativa fiscal vigente."
    ),
}


def _parse(path: Path) -> dict[str, str]:
    """``## ID`` headings followed by the text; HTML comments are metadata."""
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    blocks: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                blocks[current] = " ".join(" ".join(buf).split())
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line.strip())
    if current is not None:
        blocks[current] = " ".join(" ".join(buf).split())
    return blocks


def test_disclosure_texts_are_exact(service_root: Path) -> None:
    path = service_root / "prompts" / "system" / "disclosures.es-MX.md"
    assert path.exists(), "prompts/system/disclosures.es-MX.md is missing"
    blocks = _parse(path)
    for disclosure_id, expected in EXPECTED.items():
        assert disclosure_id in blocks, f"missing disclosure {disclosure_id}"
        assert blocks[disclosure_id] == expected, (
            f"{disclosure_id} text changed; legal review required.\n"
            f"expected: {expected}\nactual:   {blocks[disclosure_id]}"
        )


def test_disclosure_file_is_versioned(service_root: Path) -> None:
    path = service_root / "prompts" / "system" / "disclosures.es-MX.md"
    assert re.search(r"<!--\s*version:\s*\S+", path.read_text(encoding="utf-8")), (
        "disclosures file must carry a version marker; the version is recorded per turn"
    )
