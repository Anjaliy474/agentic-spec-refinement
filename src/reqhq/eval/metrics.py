from __future__ import annotations


def prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def completeness_penalty(implied: set[str], covered: set[str]) -> float:
    """Share of NFR categories implied by the PRD that the spec omits."""
    if not implied:
        return 0.0
    return len(implied - covered) / len(implied)
