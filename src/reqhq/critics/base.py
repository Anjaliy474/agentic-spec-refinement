from __future__ import annotations

from abc import ABC, abstractmethod

from reqhq.models import Finding, Requirement


class Critic(ABC):
    """Reviews a draft spec against the PRD and reports missing or vague NFRs."""

    name: str

    @abstractmethod
    def review(self, prd_sentences: dict[str, str], draft: list[Requirement]) -> list[Finding]:
        ...
