"""Environment checks without ranking gaps."""

from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import has_testrisk_table
from .discover import (
    COVERAGE_CANDIDATES,
    GENERATE_COVERAGE,
    RANK_CHANGED,
    find_coverage_file,
    resolve_repo_path,
)
from .errors import GapError
from .freshness import stale_sources
from .gitdiff import changed_lines, is_git_repo, resolve_base
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
    config_file: Path | None = None
    stale_coverage: bool = False
    stale_files: tuple[str, ...] = ()
    generate: str = GENERATE_COVERAGE
    next_command: str = RANK_CHANGED

    def to_dict(self) -> dict[str, object]:
        return {
            "python": self.python,
            "version": self.version,
            "repo": str(self.repo),
            "coverage_file": None if self.coverage_file is None else self.coverage_file.as_posix(),
            "coverage_error": self.coverage_error,
            "git": self.git,
            "base": self.base,
            "config_file": None if self.config_file is None else self.config_file.as_posix(),
            "stale_coverage": self.stale_coverage,
            "stale_files": list(self.stale_files),
            "generate": self.generate,
            "next": self.next_command,
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
    config_file = Path("pyproject.toml") if has_testrisk_table(repo) else None
    stale = False
    stale_files: tuple[str, ...] = ()
    if coverage_file is not None:
        coverage_abs = coverage_file if coverage_file.is_absolute() else repo / coverage_file
        changed = changed_lines(repo, base) if git else {}
        stale_paths = stale_sources(repo, coverage_abs, changed)
        stale = bool(stale_paths)
        stale_files = tuple(path.as_posix() for path in stale_paths)
    return DoctorReport(
        python=sys.version.split()[0],
        version=__version__,
        repo=repo,
        coverage_file=coverage_file,
        coverage_error=coverage_error,
        git=git,
        base=base,
        config_file=config_file,
        stale_coverage=stale,
        stale_files=stale_files,
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
        if report.stale_coverage:
            ui.kv("Stale", "coverage older than files changed on this branch")
    else:
        ui.kv("Coverage", report.coverage_error or "not found")
        ui.note("Looked for: " + ", ".join(COVERAGE_CANDIDATES), persist=True)
    ui.kv("Git", "yes" if report.git else "no")
    if report.base:
        ui.kv("Diff base", report.base)
    if report.config_file is not None:
        ui.kv("Config", report.config_file.as_posix())
    ui.blank()
    if report.ok:
        if report.stale_coverage:
            ui.note(f"Refresh coverage with: {report.generate}", persist=True)
        ui.success("Ready to rank test gaps.")
        ui.note(f"Next: {report.next_command}", persist=True)
        return 0
    ui.error("Generate coverage data, then re-run testrisk.")
    ui.note(f"  {report.generate}", persist=True)
    ui.note(f"  {report.next_command}", persist=True)
    return 1
