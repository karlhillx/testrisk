"""Immutable report types shared by the library and CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Risk(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


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

    @property
    def statements(self) -> frozenset[int]:
        return self.executed_lines | self.missing_lines


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

    @property
    def qualname(self) -> str:
        return f"{self.path.as_posix()}::{self.name}"

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
            "existing_tests": [path.as_posix() for path in self.existing_tests],
            "suggested_test": self.suggested_test.as_posix(),
            "score": round(self.score, 3),
            "risk": self.risk.value,
        }


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

    def to_dict(self) -> dict[str, object]:
        payload = {
            "version": self.version,
            "root": str(self.root),
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
