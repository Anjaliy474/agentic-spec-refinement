from __future__ import annotations

from collections import defaultdict

from reqhq.models import Finding, Question


def select_questions(findings: list[Finding]) -> list[Question]:
    """Return questions only for missing business context or cross-critic conflicts.

    Placeholder rule: a conflict is two or more critics flagging the same PRD sentence.
    To be replaced by the real conflict detector.
    """
    questions: list[Question] = []
    by_sentence: dict[str | None, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.needs_business_context:
            questions.append(
                Question(id=f"q{len(questions) + 1}", text=f.description,
                         reason="missing_context", findings=[f])
            )
        else:
            by_sentence[f.prd_sentence_id].append(f)
    for sid, group in by_sentence.items():
        if sid is not None and len({f.critic for f in group}) > 1:
            questions.append(
                Question(id=f"q{len(questions) + 1}",
                         text=f"Critics disagree on PRD sentence {sid}",
                         reason="conflict", findings=group)
            )
    return questions
