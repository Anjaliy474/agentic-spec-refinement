"""Orchestrator step 1: extract draft functional requirements from a PRD."""

from __future__ import annotations

from reqhq.llm import LLM
from reqhq.models import Requirement, SourceKind, TraceLink
from reqhq.prd import PRD

SYSTEM = (
    "You are a requirements engineer. You turn product requirement documents into "
    "precise, testable functional requirements. You never invent features the "
    "document does not mention."
)

PROMPT = """Below is a product requirements document. Each sentence has an id in brackets.

{prd}

Extract the FUNCTIONAL requirements: what the system must do. Rules:
- One behaviour per requirement, written as "The system shall ...".
- Every requirement cites the sentence ids it comes from in "sources".
- Do not include quality attributes (speed, security, availability, usability); another step handles those.
- Do not add anything the document does not state or clearly imply.

Reply with JSON only, in this shape:
{{"requirements": [{{"text": "The system shall ...", "sources": ["s1"]}}]}}"""


def extract_frs(llm: LLM, prd: PRD) -> list[Requirement]:
    data = llm.complete_json(PROMPT.format(prd=prd.numbered()), system=SYSTEM, tag="orchestrator:extract")
    items = data.get("requirements", []) if isinstance(data, dict) else data
    reqs: list[Requirement] = []
    for item in items or []:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        sources = [s for s in item.get("sources", []) if s in prd.sentences]
        reqs.append(
            Requirement(
                id=f"FR{len(reqs) + 1}",
                text=item["text"].strip(),
                is_functional=True,
                trace=[TraceLink(kind=SourceKind.PRD, ref=s) for s in sources],
            )
        )
    return reqs
