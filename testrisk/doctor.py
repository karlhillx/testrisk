"""Environment checks without ranking gaps."""

from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .discover import COVERAGE_CANDIDATES, find_coverage_file, resolve_repo_path
from .errors import GapError
from .gitdiff import is_git_repo, resolve_base
from .ui import get_ui
from .version import __version__


@dataclass(frozen=True)
class DoctorReport:
    python: str
    version: str
    repo: Path
    coverage_file: Path | None
    coverage_error: str | None
    git: bool
    base: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "python": self.python,
            "version": self.version,
            "repo": str(self.repo),
            "coverage_file": None if self.coverage_file is None else self.coverage_file.as_posix(),
            "coverage_error": self.coverage_error,
            "git": self.git,
            "base": self.base,
        }

    @property
    def ok(self) -> bool:
        return self.coverage_file is not None


def inspect_environment(repo_arg: str, coverage: str | None = None) -> DoctorReport:
    repo = resolve_repo_path(repo_arg)
    coverage_file: Path | None = None
    coverage_error: str | None = None
    try:
        coverage_file = find_coverage_file(
            repo,
            None if coverage is None else Path(coverage),
        )
        with contextlib.suppress(ValueError):
            coverage_file = coverage_file.relative_to(repo)
    except GapError as exc:
        coverage_error = str(exc).split("\n", 1)[0]
    git = is_git_repo(repo)
    base = resolve_base(repo, None) if git else None
    return DoctorReport(
        python=sys.version.split()[0],
        version=__version__,
        repo=repo,
        coverage_file=coverage_file,
        coverage_error=coverage_error,
        git=git,
        base=base,
    )


def print_doctor(report: DoctorReport, *, json_output: bool = False) -> int:
    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1

    ui = get_ui()
    ui.title(f"testrisk {report.version}")
    ui.blank()
    ui.kv("Python", report.python)
    ui.kv("Repository", str(report.repo))
    if report.coverage_file is not None:
        ui.kv("Coverage", report.coverage_file.as_posix())
    else:
        ui.kv("Coverage", report.coverage_error or "not found")
        ui.note("Looked for: " + ", ".join(COVERAGE_CANDIDATES), persist=True)
    ui.kv("Git", "yes" if report.git else "no")
    if report.base:
        ui.kv("Diff base", report.base)
    ui.blank()
    if report.ok:
        ui.success("Ready to rank test gaps.")
        return 0
    ui.error("Generate coverage data, then re-run testrisk.")
    return 1
