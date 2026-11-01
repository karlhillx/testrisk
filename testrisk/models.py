"""Immutable report types shared by the library and CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

SCHEMA = "testrisk.gap/v2"


class Risk(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TestKind(StrEnum):
    """How related tests stand relative to a gap. Not a pytest test class."""

    __test__ = False
    NONE = "none"
    INDIRECT = "indirect"
    WEAK = "weak"
    MEANINGFUL = "meaningful"


_RISK_RANK = {Risk.LOW: 0, Risk.MEDIUM: 1, Risk.HIGH: 2}


def parse_risk(value: str | Risk) -> Risk:
    """Parse a risk label; raises ``ValueError`` if unknown."""
    if isinstance(value, Risk):
        return value
    key = value.strip().upper()
    try:
        return Risk(key)
    except ValueError:
        raise ValueError(f"Unknown risk {value!r}; use LOW, MEDIUM, or HIGH") from None


def risk_rank(risk: Risk) -> int:
    return _RISK_RANK[risk]


def risk_at_least(risk: Risk, floor: Risk) -> bool:
    return _RISK_RANK[risk] >= _RISK_RANK[floor]


def worst_risk(risks: tuple[Risk, ...] | list[Risk]) -> Risk | None:
    if not risks:
        return None
    return max(risks, key=risk_rank)


@dataclass(frozen=True)
class ScoreParts:
    """How a gap score was assembled. Defaults match :func:`testrisk.rank.score_gap`."""

    missing_lines: float = 0.0
    missing_branches: float = 0.0
    complexity: float = 0.0
    changed_uncovered: float = 0.0
    no_tests: float = 0.0
    churn: float = 0.0
    fan_in: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.missing_lines
            + self.missing_branches
            + self.complexity
            + self.changed_uncovered
            + self.no_tests
            + self.churn
            + self.fan_in
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "missing_lines": round(self.missing_lines, 3),
            "missing_branches": round(self.missing_branches, 3),
            "complexity": round(self.complexity, 3),
            "changed_uncovered": round(self.changed_uncovered, 3),
            "no_tests": round(self.no_tests, 3),
            "churn": round(self.churn, 3),
            "fan_in": round(self.fan_in, 3),
            "total": round(self.total, 3),
        }


@dataclass(frozen=True)
class BranchGap:
    """One uncovered branch, as coverage.py records it."""

    line: int
    dest: int

    def describe(self) -> str:
        if self.dest < 0:
            return f"line {self.line}: exception/exit branch"
        if self.dest == 0:
            return f"line {self.line}: false branch"
        return f"line {self.line}: branch to line {self.dest}"


@dataclass(frozen=True)
class FileCoverage:
    """Normalized per-file coverage used by ranking."""

    path: Path
    executed_lines: frozenset[int]
    missing_lines: frozenset[int]
    excluded_lines: frozenset[int]
    missing_branches: tuple[BranchGap, ...] = ()
    contexts: dict[int, tuple[str, ...]] = field(default_factory=dict)

    @property
    def statements(self) -> frozenset[int]:
        return self.executed_lines | self.missing_lines

    @property
    def has_contexts(self) -> bool:
        return any(self.contexts.values())


@dataclass(frozen=True)
class CoverageSnapshot:
    """Project-level coverage plus per-file detail."""

    files: tuple[FileCoverage, ...]
    source: Path
    line_percent: float
    branch_percent: float | None
    covered_lines: int
    statements: int
    covered_branches: int | None
    branches: int | None


@dataclass(frozen=True)
class FunctionSpan:
    """A function or method (or ``<module>``) in a source file."""

    path: Path
    name: str
    start: int
    end: int
    complexity: int

    @property
    def qualname(self) -> str:
        return f"{self.path.as_posix()}::{self.name}"


@dataclass(frozen=True)
class Gap:
    """One ranked unit of untested behavior."""

    path: Path
    name: str
    missing_lines: tuple[int, ...]
    missing_branches: tuple[BranchGap, ...]
    complexity: int
    changed_uncovered: tuple[int, ...]
    has_tests: bool
    existing_tests: tuple[Path, ...]
    suggested_test: Path
    score: float
    risk: Risk
    score_parts: ScoreParts = field(default_factory=ScoreParts)
    weak_tests: tuple[Path, ...] = ()
    weak_reasons: tuple[str, ...] = ()
    test_kind: TestKind | None = None
    executed_by: tuple[str, ...] = ()
    churn: int = 0
    fan_in: int = 0

    @property
    def qualname(self) -> str:
        return f"{self.path.as_posix()}::{self.name}"

    @property
    def kind(self) -> TestKind:
        if self.test_kind is not None:
            return self.test_kind
        if self.has_meaningful_tests:
            return TestKind.MEANINGFUL
        if self.weak_tests:
            return TestKind.WEAK
        return TestKind.NONE

    @property
    def has_meaningful_tests(self) -> bool:
        if not self.has_tests or not self.existing_tests:
            return False
        weak = set(self.weak_tests)
        return any(path not in weak for path in self.existing_tests)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path.as_posix(),
            "name": self.name,
            "qualname": self.qualname,
            "missing_lines": list(self.missing_lines),
            "missing_line_ranges": format_line_ranges(self.missing_lines),
            "missing_branches": [
                {"line": branch.line, "dest": branch.dest, "detail": branch.describe()}
                for branch in self.missing_branches
            ],
            "complexity": self.complexity,
            "changed_uncovered": list(self.changed_uncovered),
            "has_tests": self.has_tests,
            "has_meaningful_tests": self.has_meaningful_tests,
            "test_kind": self.kind.value,
            "existing_tests": [path.as_posix() for path in self.existing_tests],
            "weak_tests": [path.as_posix() for path in self.weak_tests],
            "weak_reasons": list(self.weak_reasons),
            "executed_by": list(self.executed_by),
            "churn": self.churn,
            "fan_in": self.fan_in,
            "suggested_test": self.suggested_test.as_posix(),
            "score": round(self.score, 3),
            "score_parts": self.score_parts.to_dict(),
            "risk": self.risk.value,
        }


@dataclass(frozen=True)
class Totals:
    """Counts for the filtered gap set (before ``--top``)."""

    matched: int = 0
    shown: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    none: int = 0
    indirect: int = 0
    weak: int = 0
    meaningful: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "matched": self.matched,
            "shown": self.shown,
            "risk": {"HIGH": self.high, "MEDIUM": self.medium, "LOW": self.low},
            "checks": {
                "none": self.none,
                "indirect": self.indirect,
                "weak": self.weak,
                "meaningful": self.meaningful,
            },
        }


def totals_from_gaps(gaps: tuple[Gap, ...] | list[Gap], *, shown: int | None = None) -> Totals:
    items = tuple(gaps)
    return Totals(
        matched=len(items),
        shown=len(items) if shown is None else shown,
        high=sum(1 for gap in items if gap.risk is Risk.HIGH),
        medium=sum(1 for gap in items if gap.risk is Risk.MEDIUM),
        low=sum(1 for gap in items if gap.risk is Risk.LOW),
        none=sum(1 for gap in items if gap.kind is TestKind.NONE),
        indirect=sum(1 for gap in items if gap.kind is TestKind.INDIRECT),
        weak=sum(1 for gap in items if gap.kind is TestKind.WEAK),
        meaningful=sum(1 for gap in items if gap.kind is TestKind.MEANINGFUL),
    )


@dataclass(frozen=True)
class ChangedCoverage:
    """Coverage restricted to executable lines that git says changed."""

    percent: float | None
    covered: int
    statements: int
    missing: tuple[int, ...] = ()


@dataclass(frozen=True)
class GapReport:
    """Full analysis result."""

    version: str
    root: Path
    coverage: CoverageSnapshot
    gaps: tuple[Gap, ...]
    changed: ChangedCoverage | None
    suggested_target: Path | None
    coverage_source: Path = field(default_factory=lambda: Path("."))
    matched: int = 0
    worst_risk: Risk | None = None
    weak_matched: int = 0
    totals: Totals = field(default_factory=Totals)
    changed_only: bool = False
    stale_coverage: bool = False
    has_contexts: bool = False
    waived: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema": SCHEMA,
            "version": self.version,
            "root": str(self.root),
            "matched": self.matched,
            "weak_matched": self.weak_matched,
            "totals": self.totals.to_dict(),
            "worst_risk": None if self.worst_risk is None else self.worst_risk.value,
            "coverage": {
                "source": self.coverage.source.as_posix(),
                "percent": round(self.coverage.line_percent, 3),
                "branch_percent": (
                    None
                    if self.coverage.branch_percent is None
                    else round(self.coverage.branch_percent, 3)
                ),
                "covered_lines": self.coverage.covered_lines,
                "statements": self.coverage.statements,
                "covered_branches": self.coverage.covered_branches,
                "branches": self.coverage.branches,
            },
            "changed": None
            if self.changed is None
            else {
                "percent": None if self.changed.percent is None else round(self.changed.percent, 3),
                "covered": self.changed.covered,
                "statements": self.changed.statements,
                "missing": self.changed.statements - self.changed.covered,
            },
            "gaps": [gap.to_dict() for gap in self.gaps],
            "suggested_target": (
                None if self.suggested_target is None else self.suggested_target.as_posix()
            ),
            "changed_only": self.changed_only,
            "stale_coverage": self.stale_coverage,
            "has_contexts": self.has_contexts,
            "waived": list(self.waived),
        }
        return payload


def format_line_ranges(lines: tuple[int, ...] | list[int]) -> str:
    """Turn ``[84, 85, 86, 103]`` into ``84-86, 103``."""
    if not lines:
        return ""
    ordered = sorted(set(lines))
    ranges: list[str] = []
    start = prev = ordered[0]
    for number in ordered[1:]:
        if number == prev + 1:
            prev = number
            continue
        ranges.append(_one_range(start, prev))
        start = prev = number
    ranges.append(_one_range(start, prev))
    return ", ".join(ranges)


def _one_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"
