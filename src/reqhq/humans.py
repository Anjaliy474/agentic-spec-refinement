"""Who answers the questions: nobody, a person at the terminal, or a simulated oracle.

The oracle answers from the reference specification, which keeps experiments
repeatable (see the proposal's evaluation plan). It says it does not know when
the reference does not settle the question, so it cannot leak facts that a
real product owner would not have written down.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from reqhq.llm import LLM
from reqhq.models import Question
from reqhq.prd import PRD


class Human(ABC):
    @abstractmethod
    def answer(self, question: Question, prd: PRD) -> str | None:
        """Return an answer, or None if the human cannot or will not answer."""


class NoHuman(Human):
    def answer(self, question: Question, prd: PRD) -> str | None:
        return None


class InteractiveHuman(Human):
    """Asks at the terminal. An empty reply means "don't know"."""

    def __init__(self, input_fn=input, print_fn=print):
        self.input_fn = input_fn
        self.print_fn = print_fn

    def answer(self, question: Question, prd: PRD) -> str | None:
        self.print_fn(f"\n[{question.id}] ({question.reason}) {question.text}")
        reply = self.input_fn("> ").strip()
        return reply or None


ORACLE_SYSTEM = (
    "You play a product owner. You answer ONLY from the reference specification you are "
    "given. If it does not answer the question, you reply exactly UNKNOWN."
)

ORACLE_PROMPT = """Reference specification:
---
{reference}
---

Question from the requirements team:
{question}

Answer in one or two sentences using only facts from the reference specification,
or reply exactly UNKNOWN."""


class OracleHuman(Human):
    def __init__(self, llm: LLM, reference_spec: str):
        self.llm = llm
        self.reference = reference_spec

    def answer(self, question: Question, prd: PRD) -> str | None:
        reply = self.llm.complete(
            ORACLE_PROMPT.format(reference=self.reference, question=question.text),
            system=ORACLE_SYSTEM,
            tag="oracle",
        ).strip()
        return None if not reply or reply.upper().startswith("UNKNOWN") else reply
