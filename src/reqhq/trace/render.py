"""Render a spec as Markdown with a trace link on every line."""

from __future__ import annotations

from reqhq.models import Requirement, SourceKind, Spec
from reqhq.prd import PRD


def _trace(r: Requirement) -> str:
    parts = []
    for t in r.trace:
        if t.kind == SourceKind.PRD:
            parts.append(f"PRD {t.ref}")
        elif t.kind == SourceKind.CRITIC:
            parts.append(f"critic: {t.ref}")
        else:
            parts.append(f"answer {t.ref}")
    return ", ".join(parts) or "untraced"


def render_markdown(spec: Spec, prd: PRD | None = None) -> str:
    frs = [r for r in spec.requirements if r.is_functional]
    nfrs = [r for r in spec.requirements if not r.is_functional]
    lines = [f"# Specification: {spec.prd_id}", "", "## Functional requirements", ""]
    lines += [f"- **{r.id}** {r.text}  \n  _from: {_trace(r)}_" for r in frs] or ["_None._"]

    lines += ["", "## Non-functional requirements", ""]
    by_cat: dict[str, list[Requirement]] = {}
    for r in nfrs:
        by_cat.setdefault(r.category.value if r.category else "other", []).append(r)
    for cat in sorted(by_cat):
        lines += [f"### {cat.capitalize()}", ""]
        for r in by_cat[cat]:
            flag = " ⚠️ _open: needs product-owner input_" if r.open_issue else ""
            lines.append(f"- **{r.id}** {r.text}{flag}  \n  _from: {_trace(r)}_")
        lines.append("")
    if not nfrs:
        lines += ["_None._", ""]

    if spec.questions_asked:
        lines += ["## Questions asked", ""]
        for q in spec.questions_asked:
            lines.append(f"- **{q.id}** ({q.reason}) {q.text}  \n  Answer: {q.answer or '_no answer_'}")
        lines.append("")

    if prd is not None:
        lines += ["## PRD sentences", ""]
        lines += [f"- `{sid}` {text}" for sid, text in prd.sentences.items()]
        lines.append("")
    return "\n".join(lines)
