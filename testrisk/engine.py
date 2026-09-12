"""Orchestrate coverage + AST + git + ranking into a ``GapReport``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ast_index import index_file, innermost, module_complexity
from .coverage_data import load_coverage
from .discover import (
    find_coverage_file,
    matches_filter,
    relativize,
    resolve_repo_path,
    same_relpath,
)
from .gitdiff import changed_lines, resolve_base
from .models import (
    BranchGap,
    ChangedCoverage,
    FileCoverage,
    FunctionSpan,
    Gap,
    GapReport,
)
from .rank import score_gap, sort_gaps
from .tests_map import is_test_path, iter_test_files, related_tests, suggested_test_path
from .version import __version__


@dataclass(frozen=True)
class Options:
    """Inputs for :func:`analyze`."""

    root: Path | str = "."
    coverage: Path | str | None = None
    changed_only: bool = False
    base: str | None = None
    files: tuple[str, ...] = ()
    top: int = 10


@dataclass
class _Bucket:
    span: FunctionSpan
    missing_lines: set[int] = field(default_factory=set)
    missing_branches: list[BranchGap] = field(default_factory=list)


def analyze(
    root: Path | str = ".",
    *,
    coverage: Path | str | None = None,
    changed_only: bool = False,
    base: str | None = None,
    files: tuple[str, ...] | list[str] | None = None,
    top: int = 10,
    options: Options | None = None,
) -> GapReport:
    """
    Rank uncovered production behavior in a checkout.

    Parameters
    ----------
    root:
        Project directory (walk-up applies when this is ``"."``).
    coverage:
        Optional ``coverage.json``, ``coverage.xml``, or ``.coverage``.
    changed_only:
        Keep gaps that intersect the git change set.
    base:
        Git ref to diff against (default: ``origin/main`` / ``main`` / ``HEAD``).
    files:
        Restrict ranking to these source paths.
    top:
        How many gaps to keep (``0`` means all).
    options:
        If given, the other arguments are ignored.

    Raises
    ------
    GapError
        No readable coverage artifact, or the coverage file is invalid.
    """
    chosen = options or Options(
        root=root,
        coverage=coverage,
        changed_only=changed_only,
        base=base,
        files=tuple(files or ()),
        top=top,
    )
    repo = resolve_repo_path(str(chosen.root))
    coverage_path = find_coverage_file(
        repo,
        None if chosen.coverage is None else Path(chosen.coverage),
    )
    snapshot = load_coverage(repo, coverage_path)
    filters = tuple(Path(item) for item in chosen.files)
    git_base = resolve_base(repo, chosen.base)
    changed = changed_lines(repo, git_base)
    inventory = iter_test_files(repo)

    gaps: list[Gap] = []
    changed_statements = 0
    changed_covered = 0
    changed_missing: list[int] = []

    for file_cov in snapshot.files:
        if is_test_path(file_cov.path):
            continue
        if not _file_matches(file_cov.path, filters):
            continue
        source = repo / file_cov.path
        if not source.is_file():
            continue
        rel_changed = _changed_for(file_cov.path, changed)
        covered_here, missing_here = _changed_statement_counts(file_cov, rel_changed)
        changed_statements += covered_here + missing_here
        changed_covered += covered_here
        if missing_here:
            changed_missing.extend(sorted(file_cov.missing_lines & rel_changed))
        gaps.extend(
            _gaps_for_file(
                repo=repo,
                file_cov=file_cov,
                source=source,
                rel_changed=rel_changed,
                inventory=inventory,
            )
        )

    ranked = sort_gaps(gaps)
    if chosen.changed_only:
        ranked = tuple(gap for gap in ranked if gap.changed_uncovered)
    if chosen.top > 0:
        ranked = ranked[: chosen.top]

    suggested = ranked[0].suggested_test if ranked else None
    if ranked and ranked[0].existing_tests:
        suggested = ranked[0].existing_tests[0]

    changed_cov = None
    if git_base is not None:
        percent = 100.0 if changed_statements == 0 else 100.0 * changed_covered / changed_statements
        changed_cov = ChangedCoverage(
            percent=percent,
            covered=changed_covered,
            statements=changed_statements,
            missing=tuple(changed_missing),
        )

    return GapReport(
        version=__version__,
        root=repo,
        coverage=snapshot,
        gaps=ranked,
        changed=changed_cov,
        suggested_target=suggested,
        coverage_source=snapshot.source,
    )


def _file_matches(path: Path, filters: tuple[Path, ...]) -> bool:
    if not filters:
        return True
    return any(matches_filter(path, item) for item in filters)


def _changed_for(path: Path, changed: dict[Path, frozenset[int]]) -> frozenset[int]:
    if path in changed:
        return changed[path]
    for candidate, lines in changed.items():
        if same_relpath(path, candidate):
            return lines
    return frozenset()


def _changed_statement_counts(file_cov: FileCoverage, changed: frozenset[int]) -> tuple[int, int]:
    if not changed:
        return 0, 0
    statements = file_cov.statements & changed
    missing = file_cov.missing_lines & changed
    covered = len(statements - missing)
    return covered, len(missing)


def _gaps_for_file(
    *,
    repo: Path,
    file_cov: FileCoverage,
    source: Path,
    rel_changed: frozenset[int],
    inventory: tuple[Path, ...],
) -> list[Gap]:
    rel = relativize(file_cov.path, repo)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    spans = index_file(rel, text)
    buckets: dict[str, _Bucket] = {}

    def bucket_for(line: int) -> _Bucket:
        span = innermost(line, spans)
        if span is None:
            span = FunctionSpan(
                path=rel,
                name="<module>",
                start=line,
                end=line,
                complexity=module_complexity(rel, text),
            )
        key = span.qualname
        if key not in buckets:
            buckets[key] = _Bucket(span=span)
        return buckets[key]

    for line in file_cov.missing_lines:
        bucket_for(line).missing_lines.add(line)
    for branch in file_cov.missing_branches:
        bucket_for(branch.line).missing_branches.append(branch)

    # Collapse multiple synthetic <module> buckets into one.
    module_keys = [key for key in buckets if key.endswith("::<module>")]
    if len(module_keys) > 1:
        primary = buckets[module_keys[0]]
        for key in module_keys[1:]:
            extra = buckets.pop(key)
            primary.missing_lines.update(extra.missing_lines)
            primary.missing_branches.extend(extra.missing_branches)
        lines = primary.missing_lines
        primary.span = FunctionSpan(
            path=rel,
            name="<module>",
            start=min(lines) if lines else primary.span.start,
            end=max(lines) if lines else primary.span.end,
            complexity=primary.span.complexity,
        )

    gaps: list[Gap] = []
    for bucket in buckets.values():
        unique_branches: list[BranchGap] = []
        seen: set[tuple[int, int]] = set()
        for branch in bucket.missing_branches:
            pair = (branch.line, branch.dest)
            if pair in seen:
                continue
            seen.add(pair)
            unique_branches.append(branch)
        missing = tuple(sorted(bucket.missing_lines))
        if not missing and not unique_branches:
            continue
        changed_uncovered = tuple(line for line in missing if line in rel_changed)
        existing = related_tests(repo, rel, bucket.span.name, inventory=inventory)
        suggested = existing[0] if existing else suggested_test_path(rel)
        value, risk = score_gap(
            missing_lines=len(missing),
            missing_branches=len(unique_branches),
            complexity=bucket.span.complexity,
            changed_uncovered=len(changed_uncovered),
            has_tests=bool(existing),
        )
        gaps.append(
            Gap(
                path=rel,
                name=bucket.span.name,
                missing_lines=missing,
                missing_branches=tuple(unique_branches),
                complexity=bucket.span.complexity,
                changed_uncovered=changed_uncovered,
                has_tests=bool(existing),
                existing_tests=existing,
                suggested_test=suggested,
                score=value,
                risk=risk,
            )
        )
    return gaps
