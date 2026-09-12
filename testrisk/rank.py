"""Score and order test gaps by likely value."""

from __future__ import annotations

from .models import Gap, Risk


def score_gap(
    *,
    missing_lines: int,
    missing_branches: int,
    complexity: int,
    changed_uncovered: int,
    has_tests: bool,
) -> tuple[float, Risk]:
    """
    Combine gap signals into a single ranking score.

    Weights favor changed uncovered lines and untested branches over raw
    missing-line count, then lift complex functions and code with no tests.
    """
    value = (
        missing_lines * 1.0
        + missing_branches * 2.0
        + max(0, complexity - 1) * 0.75
        + changed_uncovered * 3.0
        + (0.0 if has_tests else 4.0)
    )
    return value, classify_risk(
        value=value,
        complexity=complexity,
        missing_branches=missing_branches,
        changed_uncovered=changed_uncovered,
        missing_lines=missing_lines,
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
