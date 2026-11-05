"""Gap and conflict check: decides which findings become questions for the human.

Modes (these map onto the experimental conditions):
- ``none``: never ask (B3, pipeline without human input).
- ``targeted``: ask only about missing business context and cross-critic conflicts (full pipeline).
- ``all``: ask the human to review every finding (B4, ask-everything review).
"""

from __future__ import annotations

from dataclasses import dataclass

from reqhq.llm import LLM
from reqhq.models import Finding, Question

MODES = ("none", "targeted", "all")


@dataclass
class Conflict:
    a: int  # index into the findings list
    b: int
    explanation: str
    question: str


CONFLICT_SYSTEM = (
    "You check whether quality requirements proposed by different reviewers contradict "
    "each other, so that satisfying one makes another harder or impossible."
)

CONFLICT_PROMPT = """Proposed non-functional requirements, each from a different reviewer:

{items}

List the pairs that genuinely conflict: meeting one would make meeting the other
difficult or impossible (for example, strong encryption on every request versus a tight
latency target, or long data retention versus a privacy limit). Ignore pairs that are
merely about different topics.

For each conflict give the two ids, a one-sentence explanation, and the one question
the product owner must answer to resolve it.
Reply with JSON only: {{"conflicts": [{{"a": 0, "b": 3, "explanation": "...", "question": "..."}}]}}
Reply {{"conflicts": []}} if there are none."""


def detect_conflicts(llm: LLM, findings: list[Finding]) -> list[Conflict]:
    if len({f.critic for f in findings}) < 2:
        return []
    items = "\n".join(
        f"[{i}] ({f.critic}) {f.proposed_requirement or f.description}" for i, f in enumerate(findings)
    )
    data = llm.try_complete_json(
        CONFLICT_PROMPT.format(items=items), system=CONFLICT_SYSTEM, tag="gate:conflicts"
    )
    raw = data.get("conflicts", []) if isinstance(data, dict) else data
    conflicts: list[Conflict] = []
    seen: set[tuple[int, int]] = set()
    for c in raw if isinstance(raw, list) else []:
        try:
            a, b = int(c["a"]), int(c["b"])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        pair = (min(a, b), max(a, b))
        if a == b or pair in seen or not (0 <= a < len(findings) and 0 <= b < len(findings)):
            continue
        if findings[a].critic == findings[b].critic:
            continue  # by definition a conflict is between critics
        seen.add(pair)
        conflicts.append(
            Conflict(pair[0], pair[1], str(c.get("explanation", "")), str(c.get("question", "")).strip())
        )
    return conflicts


def select_questions(
    findings: list[Finding], conflicts: list[Conflict], mode: str = "targeted"
) -> list[Question]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode == "none":
        return []

    questions: list[Question] = []

    def add(text: str, reason: str, group: list[Finding]) -> None:
        questions.append(Question(id=f"Q{len(questions) + 1}", text=text, reason=reason, findings=group))

    in_conflict = {i for c in conflicts for i in (c.a, c.b)}
    for c in conflicts:
        text = c.question or f"These requirements conflict: {c.explanation} Which should take priority?"
        add(text, "conflict", [findings[c.a], findings[c.b]])

    for i, f in enumerate(findings):
        if i in in_conflict:
            continue
        if f.needs_business_context and f.question:
            add(f.question, "missing_context", [f])
        elif mode == "all":
            proposal = f.proposed_requirement or f.description
            add(
                f"Reviewer ({f.critic}) suggests: \"{proposal}\". Is this right for the product? "
                "If not, what should it say?",
                "review",
                [f],
            )
    return questions
