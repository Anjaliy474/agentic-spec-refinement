import json

from reqhq.critics.prompted import PERFORMANCE, SECURITY, PromptedCritic
from reqhq.llm import FakeLLM
from reqhq.models import NFRCategory
from reqhq.prd import prd_from_text

PRD = prd_from_text("Users can book slots. The booking page should be fast.")


def critic_with(reply: dict, role=PERFORMANCE) -> PromptedCritic:
    return PromptedCritic(role, FakeLLM(lambda s, p: json.dumps(reply)))


def test_findings_are_parsed_and_cleaned():
    findings = critic_with(
        {
            "findings": [
                {
                    "category": "performance",
                    "kind": "vague",
                    "description": "'fast' has no target",
                    "prd_sentence_id": "s2",
                    "needs_business_context": True,
                    "question": "What response time is acceptable?",
                    "proposed_requirement": "The booking page shall load within <N> s.",
                },
                {"category": "nonsense", "description": "No peak load stated", "prd_sentence_id": "s42"},
                {"category": "scalability", "description": ""},
            ]
        }
    ).review(PRD, [])
    assert len(findings) == 2
    first, second = findings
    assert first.kind == "vague" and first.needs_business_context
    assert first.question == "What response time is acceptable?"
    assert second.category == NFRCategory.PERFORMANCE  # unknown category -> role default
    assert second.prd_sentence_id is None  # unknown sentence id dropped
    assert all(f.critic == "performance" for f in findings)


def test_context_flag_without_question_is_not_a_context_gap():
    [f] = critic_with(
        {"findings": [{"category": "security", "description": "x", "needs_business_context": True}]},
        role=SECURITY,
    ).review(PRD, [])
    assert not f.needs_business_context


def test_prompt_mentions_role_and_prd():
    seen = {}

    def responder(system, prompt):
        seen["system"], seen["prompt"] = system, prompt
        return '{"findings": []}'

    PromptedCritic(SECURITY, FakeLLM(responder)).review(PRD, [])
    assert "security reviewer" in seen["system"]
    assert "[s2] The booking page should be fast." in seen["prompt"]
