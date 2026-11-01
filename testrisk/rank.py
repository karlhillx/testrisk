"""Score and order test gaps by likely value."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Gap, Risk, ScoreParts


@dataclass(frozen=True)
class Weights:
    """Per-signal multipliers. Changing these changes ranking."""

    missing_lines: float = 1.0
    missing_branches: float = 2.0
    complexity: float = 0.75
    changed_uncovered: float = 3.0
    no_tests: float = 4.0
    churn: float = 0.25
    fan_in: float = 0.4


DEFAULT_WEIGHTS = Weights()


def score_gap(
    *,
    missing_lines: int,
    missing_branches: int,
    complexity: int,
    changed_uncovered: int,
    has_tests: bool,
    churn: int = 0,
    fan_in: int = 0,
    weights: Weights | None = None,
) -> tuple[float, Risk, ScoreParts]:
    """
    Combine gap signals into a single ranking score.

    Weights favor changed uncovered lines and untested branches over raw
    missing-line count, then lift complex functions and code with no tests.
    Churn and fan-in are capped so history cannot drown the coverage signals.
    """
    chosen = weights or DEFAULT_WEIGHTS
    parts = ScoreParts(
        missing_lines=missing_lines * chosen.missing_lines,
        missing_branches=missing_branches * chosen.missing_branches,
        complexity=max(0, complexity - 1) * chosen.complexity,
        changed_uncovered=changed_uncovered * chosen.changed_uncovered,
        no_tests=0.0 if has_tests else chosen.no_tests,
        churn=min(max(churn, 0), 12) * chosen.churn,
        fan_in=min(max(fan_in, 0), 10) * chosen.fan_in,
    )
    value = parts.total
    return (
        value,
        classify_risk(
            value=value,
            complexity=complexity,
            missing_branches=missing_branches,
            changed_uncovered=changed_uncovered,
            missing_lines=missing_lines,
        ),
        parts,
    )


def classify_risk(
    *,
    value: float,
    complexity: int,
    missing_branches: int,
    changed_uncovered: int,
    missing_lines: int,
) -> Risk:
    if changed_uncovered >= 5 or (complexity >= 10 and missing_branches >= 2) or value >= 16:
        return Risk.HIGH
    if value >= 8 or changed_uncovered >= 1 or (complexity >= 8 and missing_lines >= 3):
        return Risk.MEDIUM
    return Risk.LOW


def sort_gaps(gaps: list[Gap]) -> tuple[Gap, ...]:
    """Highest score first; ties prefer changed lines, branches, complexity."""
    return tuple(
        sorted(
            gaps,
            key=lambda gap: (
                -gap.score,
                -len(gap.changed_uncovered),
                -len(gap.missing_branches),
                -gap.complexity,
                -len(gap.missing_lines),
                gap.qualname,
            ),
        )
    )
