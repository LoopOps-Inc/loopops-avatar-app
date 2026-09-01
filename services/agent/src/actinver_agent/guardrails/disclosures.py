"""Legal-approved disclosure texts, loaded verbatim from
``prompts/system/disclosures.es-MX.md``.

The model may not paraphrase these; ``compliance_guard`` verifies exact-string
presence. Each text carries a version (file-level header or a per-block
override) that is recorded per turn in the evidence record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_HEADER_VERSION = re.compile(r"<!--\s*version:\s*([^\s>]+)\s*-->")
_BLOCK = re.compile(r"^##\s+([A-Z0-9_]+)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Disclosure:
    id: str
    text: str
    version: str


class DisclosureCatalogue:
    def __init__(self, disclosures: dict[str, Disclosure], default_version: str) -> None:
        self._items = disclosures
        self.default_version = default_version

    def get(self, disclosure_id: str) -> Disclosure:
        return self._items[disclosure_id]

    def texts(self, ids: list[str]) -> dict[str, tuple[str, str]]:
        return {i: (self._items[i].text, self._items[i].version) for i in ids if i in self._items}

    def ids(self) -> list[str]:
        return list(self._items)

    def __contains__(self, disclosure_id: str) -> bool:
        return disclosure_id in self._items

    def figures(self) -> set[str]:
        """Numbers that appear inside disclosure texts (never 'invented')."""
        out: set[str] = set()
        for d in self._items.values():
            out.update(re.findall(r"\d+(?:[.,]\d+)?", d.text))
        return out


def parse_disclosures(markdown: str) -> DisclosureCatalogue:
    header_match = _HEADER_VERSION.search(markdown)
    default_version = header_match.group(1) if header_match else "unversioned"
    items: dict[str, Disclosure] = {}
    matches = list(_BLOCK.finditer(markdown))
    for index, match in enumerate(matches):
        disclosure_id = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[match.end() : end].strip()
        version = default_version
        version_match = _HEADER_VERSION.match(body)
        if version_match:
            version = version_match.group(1)
            body = body[version_match.end() :].strip()
        text = " ".join(line.strip() for line in body.splitlines() if line.strip())
        items[disclosure_id] = Disclosure(id=disclosure_id, text=text, version=version)
    return DisclosureCatalogue(items, default_version)


@lru_cache(maxsize=4)
def load_disclosures(prompts_dir: str = "prompts") -> DisclosureCatalogue:
    path = Path(prompts_dir) / "system" / "disclosures.es-MX.md"
    if not path.exists():
        # Fall back to the package-relative prompts directory (installed layout).
        candidate = (
            Path(__file__).resolve().parents[3] / "prompts" / "system" / "disclosures.es-MX.md"
        )
        path = candidate if candidate.exists() else path
    return parse_disclosures(path.read_text(encoding="utf-8"))
