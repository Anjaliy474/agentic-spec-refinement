"""Orchestrator step 2: turn critic findings and human answers into final NFRs."""

from __future__ import annotations

from reqhq.llm import LLM
from reqhq.models import Finding, Question, Requirement, SourceKind, TraceLink

RESOLVE_SYSTEM = (
    "You are a requirements engineer writing measurable non-functional requirements. "
    "You use the product owner's answer exactly and do not add facts."
)

RESOLVE_PROMPT = """Reviewers raised these points:
{findings}

The product owner was asked: {question}
They answered: {answer}

Write the final non-functional requirement(s) that follow from this answer.
Each must be measurable and start with "The system shall".
Reply with JSON only: {{"requirements": [{{"text": "...", "category": "{default_category}"}}]}}"""


def _trace_for(f: Finding) -> list[TraceLink]:
    links = [TraceLink(kind=SourceKind.CRITIC, ref=f.critic)]
    if f.prd_sentence_id:
        links.insert(0, TraceLink(kind=SourceKind.PRD, ref=f.prd_sentence_id))
    return links


def assemble_nfrs(llm: LLM, findings: list[Finding], questions: list[Question]) -> list[Requirement]:
    nfrs: list[Requirement] = []

    def add(text: str, f: Finding, extra: list[TraceLink] | None = None, open_issue=False, category=None):
        nfrs.append(
            Requirement(
                id=f"NFR{len(nfrs) + 1}",
                text=text.strip(),
                is_functional=False,
                category=category or f.category,
                trace=_trace_for(f) + (extra or []),
                open_issue=open_issue,
            )
        )

    asked = {id(f) for q in questions for f in q.findings}

    for f in findings:
        if id(f) not in asked and f.proposed_requirement:
            # Not asked: either nothing was missing, or we are running without a human.
            add(f.proposed_requirement, f, open_issue=f.needs_business_context)

    for q in questions:
        lead = q.findings[0]
        if q.answer is None:
            for f in q.findings:
                if f.proposed_requirement:
                    add(f.proposed_requirement, f, open_issue=True)
            continue
        data = llm.try_complete_json(
            RESOLVE_PROMPT.format(
                findings="\n".join(
                    f"- ({f.critic}) {f.description} Proposed: {f.proposed_requirement or 'none'}"
                    for f in q.findings
                ),
                question=q.text,
                answer=q.answer,
                default_category=lead.category.value,
            ),
            system=RESOLVE_SYSTEM,
            tag="orchestrator:resolve",
        )
        items = data.get("requirements", []) if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            for f in q.findings:
                if f.proposed_requirement:
                    add(f.proposed_requirement, f, open_issue=True)
            continue
        human = [TraceLink(kind=SourceKind.HUMAN, ref=q.id)]
        for item in items:
            text = item.get("text", "") if isinstance(item, dict) else ""
            if not text.strip():
                continue
            category = item.get("category")
            try:
                category = type(lead.category)(category) if category else None
            except ValueError:
                category = None
            trace = human + [t for f in q.findings[1:] for t in _trace_for(f)]
            add(text, lead, extra=trace, category=category)
    return nfrs
