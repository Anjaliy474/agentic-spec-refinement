from __future__ import annotations

from abc import ABC, abstractmethod

from reqhq.models import Finding, Requirement
from reqhq.prd import PRD


class Critic(ABC):
    """Reviews a draft spec against the PRD and reports missing or vague NFRs."""

    name: str

    @abstractmethod
    def review(self, prd: PRD, draft: list[Requirement]) -> list[Finding]:
        ...
