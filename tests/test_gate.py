import json

import pytest

from reqhq.gating.gate import Conflict, detect_conflicts, select_questions
from reqhq.humans import InteractiveHuman, OracleHuman
from reqhq.llm import FakeLLM
from reqhq.models import Finding, NFRCategory, Question
from reqhq.prd import prd_from_text


def findings():
    return [
        Finding(critic="performance", category=NFRCategory.SCALABILITY,
                description="No expected load", needs_business_context=True,
                question="How many users at peak?"),
        Finding(critic="security", category=NFRCategory.SECURITY,
                description="Encrypt every request", proposed_requirement="Encrypt all traffic with mTLS."),
        Finding(critic="performance", category=NFRCategory.PERFORMANCE,
                description="Latency target", proposed_requirement="p95 latency under 50 ms."),
        Finding(critic="architecture", category=NFRCategory.RELIABILITY,
                description="No backups", proposed_requirement="Daily backups."),
    ]


def test_targeted_asks_only_context_and_conflicts():
    qs = select_questions(findings(), [Conflict(1, 2, "mTLS adds latency", "Which matters more?")])
    assert [(q.reason, q.text) for q in qs] == [
        ("conflict", "Which matters more?"),
        ("missing_context", "How many users at peak?"),
    ]


def test_all_mode_asks_about_every_finding_and_none_mode_asks_nothing():
    fs = findings()
    assert len(select_questions(fs, [], mode="all")) == len(fs)
    assert select_questions(fs, [], mode="none") == []
    with pytest.raises(ValueError):
        select_questions(fs, [], mode="sometimes")


def test_detect_conflicts_filters_bad_pairs():
    reply = json.dumps({"conflicts": [
        {"a": 1, "b": 2, "explanation": "x", "question": "q?"},
        {"a": 2, "b": 1, "explanation": "dup"},           # duplicate pair
        {"a": 0, "b": 2, "explanation": "same critic"},   # both performance
        {"a": 1, "b": 99},                                # out of range
        {"a": "bad"},
    ]})
    out = detect_conflicts(FakeLLM(lambda s, p: reply), findings())
    assert [(c.a, c.b) for c in out] == [(1, 2)]


def test_detect_conflicts_skips_model_call_for_single_critic():
    llm = FakeLLM(lambda s, p: "{}")
    assert detect_conflicts(llm, findings()[:1]) == []
    assert llm.usage.calls == []


def test_oracle_unknown_means_no_answer():
    prd = prd_from_text("x")
    q = Question(id="Q1", text="Peak users?", reason="missing_context")
    assert OracleHuman(FakeLLM(lambda s, p: "UNKNOWN"), "ref").answer(q, prd) is None
    assert OracleHuman(FakeLLM(lambda s, p: "About 5,000."), "ref").answer(q, prd) == "About 5,000."


def test_interactive_empty_reply_is_none():
    q = Question(id="Q1", text="?", reason="conflict")
    assert InteractiveHuman(lambda _: "  ", lambda *_: None).answer(q, prd_from_text("x")) is None
