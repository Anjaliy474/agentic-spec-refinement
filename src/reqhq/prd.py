"""Loading a PRD and splitting it into numbered sentences.

Sentence ids (``s1``, ``s2``, ...) are the anchor for every trace link, so the
split must be deterministic for a given input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|approx|incl|Mr|Ms|Dr|No|Fig)\.$", re.IGNORECASE)


@dataclass
class PRD:
    id: str
    sentences: dict[str, str]

    def numbered(self) -> str:
        """The PRD as ``[s1] text`` lines, which is how models see it."""
        return "\n".join(f"[{sid}] {text}" for sid, text in self.sentences.items())


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences; markdown headings and bullet items are their own sentence."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        para: list[str] = []
        for ln in lines:
            if re.match(r"^(#+\s|[-*+]\s|\d+[.)]\s)", ln):
                if para:
                    out.extend(_split_prose(" ".join(para)))
                    para = []
                out.extend(_split_prose(re.sub(r"^(#+|[-*+]|\d+[.)])\s+", "", ln)))
            else:
                para.append(ln)
        if para:
            out.extend(_split_prose(" ".join(para)))
    return [s for s in out if s]


def _split_prose(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text.strip())
    merged: list[str] = []
    for p in parts:
        if merged and _ABBREV.search(merged[-1]):
            merged[-1] = f"{merged[-1]} {p}"
        else:
            merged.append(p)
    return [m.strip() for m in merged if m.strip()]


def load_prd(path: str | Path, prd_id: str | None = None) -> PRD:
    path = Path(path)
    sentences = split_sentences(path.read_text(encoding="utf-8"))
    return PRD(
        id=prd_id or path.stem,
        sentences={f"s{i}": s for i, s in enumerate(sentences, start=1)},
    )


def prd_from_text(text: str, prd_id: str = "prd") -> PRD:
    return PRD(prd_id, {f"s{i}": s for i, s in enumerate(split_sentences(text), start=1)})
