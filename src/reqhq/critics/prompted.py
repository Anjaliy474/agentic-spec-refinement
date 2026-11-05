"""Prompted critics: one narrow reviewer per quality concern.

v1 critics are small models steered by a role prompt. The fine-tuned SLM
critics (trained on PROMISE NFR) will implement the same ``Critic`` interface,
so the pipeline and the experiments do not change when they are swapped in.
"""

from __future__ import annotations

from dataclasses import dataclass

from reqhq.critics.base import Critic
from reqhq.llm import LLM
from reqhq.models import Finding, NFRCategory, Requirement
from reqhq.prd import PRD


@dataclass(frozen=True)
class Role:
    name: str
    categories: tuple[NFRCategory, ...]
    focus: str


SECURITY = Role(
    "security",
    (NFRCategory.SECURITY,),
    "authentication, authorisation and roles, protection of personal or sensitive data "
    "(at rest and in transit), privacy and legal compliance, audit logging, abuse and input validation",
)
ARCHITECTURE = Role(
    "architecture",
    (NFRCategory.MAINTAINABILITY, NFRCategory.RELIABILITY, NFRCategory.OTHER),
    "availability and fault tolerance, backup and recovery, integration with external systems, "
    "data retention, portability and supported platforms, maintainability and modularity",
)
PERFORMANCE = Role(
    "performance",
    (NFRCategory.PERFORMANCE, NFRCategory.SCALABILITY, NFRCategory.USABILITY),
    "response time and latency, throughput, expected and peak load, scalability and growth, "
    "resource limits, and usability where it affects speed of use",
)

ROLES = {r.name: r for r in (SECURITY, ARCHITECTURE, PERFORMANCE)}

SYSTEM = (
    "You are a {name} reviewer of software specifications. You only comment on {focus}. "
    "You expose gaps instead of guessing: if a number or decision depends on business "
    "facts the document does not give, you say so and ask."
)

PROMPT = """Product requirements document (sentence ids in brackets):

{prd}

Draft functional requirements:
{frs}

Review this from the {name} point of view only ({focus}).
Report every non-functional requirement that is MISSING, or that the PRD states VAGUELY
(for example "fast" or "secure" with no measurable target).

For each finding give:
- "category": one of {categories}
- "kind": "missing" or "vague"
- "description": the gap in one sentence
- "prd_sentence_id": the sentence that caused it, or null if nothing in the PRD does
- "needs_business_context": true if a correct requirement needs facts only the product owner knows (expected user numbers, budgets, legal regime, target latency)
- "question": if needs_business_context is true, the one question to ask the product owner; otherwise null
- "proposed_requirement": a measurable "The system shall ..." requirement. If it needs business context, use a placeholder such as <N> for the unknown value.

Report only real gaps for this kind of system. Do not repeat functional requirements.
Reply with JSON only: {{"findings": [ ... ]}}"""


class PromptedCritic(Critic):
    def __init__(self, role: Role, llm: LLM):
        self.role = role
        self.name = role.name
        self.llm = llm

    def review(self, prd: PRD, draft: list[Requirement]) -> list[Finding]:
        frs = "\n".join(f"{r.id}: {r.text}" for r in draft) or "(none)"
        data = self.llm.try_complete_json(
            PROMPT.format(
                prd=prd.numbered(),
                frs=frs,
                name=self.role.name,
                focus=self.role.focus,
                categories=", ".join(c.value for c in self.role.categories),
            ),
            system=SYSTEM.format(name=self.role.name, focus=self.role.focus),
            tag=f"critic:{self.name}",
        )
        items = data.get("findings", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        return [f for item in items or [] if (f := self._to_finding(item, prd)) is not None]

    def _to_finding(self, item, prd: PRD) -> Finding | None:
        if not isinstance(item, dict) or not str(item.get("description", "")).strip():
            return None
        try:
            category = NFRCategory(str(item.get("category", "")).lower())
        except ValueError:
            category = self.role.categories[0]
        sid = item.get("prd_sentence_id")
        needs_ctx = bool(item.get("needs_business_context"))
        question = item.get("question") or None
        return Finding(
            critic=self.name,
            category=category,
            kind="vague" if str(item.get("kind", "")).lower() == "vague" else "missing",
            description=item["description"].strip(),
            prd_sentence_id=sid if sid in prd.sentences else None,
            needs_business_context=needs_ctx and bool(question),
            question=question if needs_ctx else None,
            proposed_requirement=(item.get("proposed_requirement") or None),
        )
