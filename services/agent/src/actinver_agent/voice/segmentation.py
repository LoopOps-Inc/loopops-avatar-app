"""Sentence segmentation for the streaming voice pipeline (docs/01-architecture/05 §4).

Deliberately dependency-free: pure text logic, importable without any SDK.
Cuts on ``. ! ? … : ;`` and on a 220-character soft limit, respecting Spanish
abbreviations and decimal numerals ("1.5 %").
"""

from __future__ import annotations

import re

_ABBREVIATIONS = (
    "Sr",
    "Sra",
    "Srta",
    "Lic",
    "Ing",
    "Dr",
    "Dra",
    "Av",
    "No",
    "Núm",
    "S.A",
    "S.A.B",
    "C.V",
    "aprox",
    "etc",
    "p.ej",
    "EE.UU",
)
_ABBREV_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(a) for a in _ABBREVIATIONS) + r")\.$",
    re.IGNORECASE,
)
_BOUNDARY_RE = re.compile(r"(?<=[.!?…:;])\s+")
_SOFT_LIMIT = 220


class SentenceSplitter:
    """Incremental splitter over a token stream.

    Emits a sentence as soon as one is complete rather than buffering the whole
    response, and refuses to cut on a decimal point or a known abbreviation.
    """

    def __init__(self, soft_limit: int = _SOFT_LIMIT) -> None:
        self._buffer = ""
        self._soft_limit = soft_limit

    def feed(self, token: str) -> list[str]:
        self._buffer += token
        out: list[str] = []
        search_from = 0
        while True:
            match = _BOUNDARY_RE.search(self._buffer, search_from)
            if match is None:
                break
            candidate = self._buffer[: match.start()].strip()
            if self._is_false_boundary(candidate):
                search_from = match.end()
                continue
            self._buffer = self._buffer[match.end() :]
            search_from = 0
            if candidate:
                out.append(candidate)

        if len(self._buffer) > self._soft_limit:
            cut = self._buffer.rfind(" ", 0, self._soft_limit)
            if cut > 0:
                out.append(self._buffer[:cut].strip())
                self._buffer = self._buffer[cut:].lstrip()
        return out

    def flush(self) -> str | None:
        remainder, self._buffer = self._buffer.strip(), ""
        return remainder or None

    @staticmethod
    def _is_false_boundary(candidate: str) -> bool:
        if _ABBREV_RE.search(candidate):
            return True
        return bool(re.search(r"\d\.$", candidate))


def split_sentences(text: str) -> list[str]:
    """Split a complete text into speakable sentences."""
    splitter = SentenceSplitter()
    out = splitter.feed(text)
    tail = splitter.flush()
    if tail:
        out.append(tail)
    return out
