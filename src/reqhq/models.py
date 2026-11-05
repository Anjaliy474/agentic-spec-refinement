"""Shared data model for requirements, critic findings, questions and trace links."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NFRCategory(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    USABILITY = "usability"
    MAINTAINABILITY = "maintainability"
    OTHER = "other"


class SourceKind(str, Enum):
    PRD = "prd"
    CRITIC = "critic"
    HUMAN = "human"


class TraceLink(BaseModel):
    kind: SourceKind
    ref: str = Field(description="PRD sentence id, critic name, or question id")


class Requirement(BaseModel):
    id: str
    text: str
    is_functional: bool
    category: NFRCategory | None = None
    trace: list[TraceLink] = Field(default_factory=list)
    open_issue: bool = Field(default=False, description="True if it still depends on an unanswered question")


class Finding(BaseModel):
    """One issue reported by a critic."""

    critic: str
    category: NFRCategory
    kind: str = Field(default="missing", description="'missing' or 'vague'")
    description: str
    prd_sentence_id: str | None = None
    needs_business_context: bool = False
    question: str | None = Field(default=None, description="What to ask a human, if context is missing")
    proposed_requirement: str | None = None


class Question(BaseModel):
    id: str
    text: str
    reason: str = Field(description="'missing_context', 'conflict' or 'review'")
    findings: list[Finding] = Field(default_factory=list)
    answer: str | None = None


class Spec(BaseModel):
    prd_id: str
    requirements: list[Requirement] = Field(default_factory=list)
    questions_asked: list[Question] = Field(default_factory=list)
