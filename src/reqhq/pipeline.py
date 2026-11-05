"""The full ReqHQ pipeline: extract -> critique -> gate -> ask -> assemble."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from reqhq.critics.base import Critic
from reqhq.gating.gate import Conflict, detect_conflicts, select_questions
from reqhq.humans import Human, NoHuman
from reqhq.llm import LLM
from reqhq.models import Finding, Spec
from reqhq.orchestrator.assemble import assemble_nfrs
from reqhq.orchestrator.extract import extract_frs
from reqhq.prd import PRD


@dataclass
class RunResult:
    spec: Spec
    findings: list[Finding]
    conflicts: list[Conflict]
    usage: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def run_pipeline(
    prd: PRD,
    orchestrator: LLM,
    critics: list[Critic],
    human: Human | None = None,
    mode: str = "targeted",
    parallel_critics: bool = True,
) -> RunResult:
    human = human or NoHuman()

    frs = extract_frs(orchestrator, prd)

    if parallel_critics and len(critics) > 1:
        with ThreadPoolExecutor(max_workers=len(critics)) as pool:
            per_critic = list(pool.map(lambda c: c.review(prd, frs), critics))
    else:
        per_critic = [c.review(prd, frs) for c in critics]
    findings = [f for fs in per_critic for f in fs]

    conflicts = detect_conflicts(orchestrator, findings) if mode != "none" else []
    questions = select_questions(findings, conflicts, mode)
    for q in questions:
        q.answer = human.answer(q, prd)

    nfrs = assemble_nfrs(orchestrator, findings, questions)
    spec = Spec(prd_id=prd.id, requirements=frs + nfrs, questions_asked=questions)

    usage = {"orchestrator": orchestrator.usage.summary()}
    warnings = list(orchestrator.warnings)
    for c in critics:
        llm = getattr(c, "llm", None)
        if llm is not None and llm is not orchestrator:
            usage[f"critic:{c.name}"] = llm.usage.summary()
            warnings += llm.warnings
    return RunResult(spec=spec, findings=findings, conflicts=conflicts, usage=usage, warnings=warnings)
