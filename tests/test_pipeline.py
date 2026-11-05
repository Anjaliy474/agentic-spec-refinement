"""End-to-end pipeline test with scripted models standing in for real ones."""

import json
from pathlib import Path

from reqhq.critics.prompted import ARCHITECTURE, PERFORMANCE, SECURITY, PromptedCritic
from reqhq.humans import Human
from reqhq.llm import FakeLLM
from reqhq.models import SourceKind
from reqhq.pipeline import run_pipeline
from reqhq.prd import load_prd
from reqhq.trace.render import render_markdown

PRD_PATH = Path(__file__).parent.parent / "data/examples/clinic_booking_prd.md"


def orchestrator_reply(system, prompt):
    if "Extract the FUNCTIONAL requirements" in prompt:
        return json.dumps({"requirements": [
            {"text": "The system shall let patients book an available slot.", "sources": ["s8"]},
            {"text": "The system shall let patients upload lab reports.", "sources": ["s13"]},
        ]})
    if "genuinely conflict" in prompt:
        return json.dumps({"conflicts": [
            {"a": 0, "b": 1, "explanation": "Encrypting uploads slows the page.",
             "question": "Is upload encryption allowed to add up to 1 s?"},
        ]})
    if "The product owner was asked" in prompt:
        return json.dumps({"requirements": [{"text": "The system shall resolve it as answered."}]})
    raise AssertionError(prompt[:80])


CRITIC_REPLIES = {
    "security": {"findings": [{
        "category": "security", "kind": "vague", "description": "'secure' is undefined",
        "prd_sentence_id": "s16",
        "proposed_requirement": "The system shall encrypt patient files at rest with AES-256.",
    }]},
    "performance": {"findings": [
        {"category": "performance", "kind": "vague", "description": "'fast' has no target",
         "prd_sentence_id": "s15",
         "proposed_requirement": "The booking page shall load within 1 s at p95."},
        {"category": "scalability", "description": "Peak load unknown", "prd_sentence_id": "s17",
         "needs_business_context": True, "question": "How many bookings per hour at flu-season peak?",
         "proposed_requirement": "The system shall handle <N> bookings per hour."},
    ]},
    "architecture": {"findings": [{
        "category": "reliability", "description": "No backup policy",
        "proposed_requirement": "The system shall back up patient data daily.",
    }]},
}


def make_critics():
    return [
        PromptedCritic(role, FakeLLM(lambda s, p, r=role.name: json.dumps(CRITIC_REPLIES[r])))
        for role in (SECURITY, PERFORMANCE, ARCHITECTURE)
    ]


class ScriptedHuman(Human):
    def __init__(self):
        self.asked = []

    def answer(self, question, prd):
        self.asked.append(question.text)
        return "About 2,000." if "bookings per hour" in question.text else "Yes."


def test_targeted_run_asks_two_questions_and_traces_everything():
    prd = load_prd(PRD_PATH)
    orch = FakeLLM(orchestrator_reply)
    human = ScriptedHuman()
    result = run_pipeline(prd, orch, make_critics(), human, mode="targeted")

    assert len(result.findings) == 4
    assert len(result.conflicts) == 1
    assert human.asked == [
        "Is upload encryption allowed to add up to 1 s?",
        "How many bookings per hour at flu-season peak?",
    ]
    reqs = result.spec.requirements
    assert all(r.trace for r in reqs), "every requirement must be traced"
    assert not any(r.open_issue for r in reqs)
    # backup finding was not asked about, so its proposal is used directly
    assert any(r.text == "The system shall back up patient data daily." for r in reqs)
    # answered questions produce requirements traced to the human answer
    assert sum(any(t.kind == SourceKind.HUMAN for t in r.trace) for r in reqs) == 2
    assert set(result.usage) == {"orchestrator", "critic:security", "critic:performance",
                                 "critic:architecture"}

    md = render_markdown(result.spec, prd)
    assert "## Questions asked" in md and "PRD s16" in md


def test_no_human_mode_marks_context_gaps_open_and_asks_nothing():
    prd = load_prd(PRD_PATH)
    result = run_pipeline(prd, FakeLLM(orchestrator_reply), make_critics(), mode="none")
    assert result.spec.questions_asked == []
    assert result.conflicts == []
    open_reqs = [r for r in result.spec.requirements if r.open_issue]
    assert [r.text for r in open_reqs] == ["The system shall handle <N> bookings per hour."]


def test_ask_everything_asks_about_every_finding():
    prd = load_prd(PRD_PATH)
    human = ScriptedHuman()
    result = run_pipeline(prd, FakeLLM(orchestrator_reply), make_critics(), human, mode="all")
    # 1 conflict (covers 2 findings) + 1 context question + 1 review question
    assert len(result.spec.questions_asked) == 3
    assert [q.reason for q in result.spec.questions_asked] == ["conflict", "missing_context", "review"]


def test_bad_critic_and_resolve_json_degrade_instead_of_crashing():
    prd = load_prd(PRD_PATH)

    def orch(system, prompt):
        if "The product owner was asked" in prompt:
            return "sorry, I can't"
        return orchestrator_reply(system, prompt)

    critics = make_critics()
    critics[2] = PromptedCritic(ARCHITECTURE, FakeLLM(lambda s, p: "not json at all"))
    result = run_pipeline(prd, FakeLLM(orch), critics, ScriptedHuman(), mode="targeted")
    assert len(result.findings) == 3  # architecture critic contributed nothing
    assert any(w.startswith("critic:architecture") for w in result.warnings)
    assert any(w.startswith("orchestrator:resolve") for w in result.warnings)
    # unresolved answers fall back to the critic proposals, flagged open
    assert any(r.open_issue for r in result.spec.requirements)
