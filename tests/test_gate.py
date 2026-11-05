from reqhq.gating.gate import select_questions
from reqhq.models import Finding, NFRCategory


def test_only_context_and_conflicts_become_questions():
    findings = [
        Finding(critic="performance", category=NFRCategory.SCALABILITY,
                description="Expected user load?", needs_business_context=True),
        Finding(critic="security", category=NFRCategory.SECURITY,
                description="Encrypt at rest", prd_sentence_id="s3"),
        Finding(critic="performance", category=NFRCategory.PERFORMANCE,
                description="p95 < 100ms", prd_sentence_id="s3"),
        Finding(critic="architecture", category=NFRCategory.MAINTAINABILITY,
                description="Vague module boundary", prd_sentence_id="s7"),
    ]
    qs = select_questions(findings)
    assert [q.reason for q in qs] == ["missing_context", "conflict"]
