"""Orchestrate coverage + AST + git + ranking into a ``GapReport``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ast_index import index_file, innermost, module_complexity
from .config import Settings, load_settings
from .coverage_data import load_coverage
from .discover import (
    DEFAULT_OMIT,
    find_coverage_file,
    matches_glob,
    omitted,
    relativize,
    resolve_repo_path,
    same_relpath,
)
from .freshness import coverage_is_stale
from .gitdiff import changed_lines, resolve_base
from .models import (
    BranchGap,
    ChangedCoverage,
    FileCoverage,
    FunctionSpan,
    Gap,
    GapReport,
    Risk,
    TestKind,
    parse_risk,
    risk_at_least,
    totals_from_gaps,
    worst_risk,
)
from .rank import Weights, score_gap, sort_gaps
from .strength import inspect_test_strength
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
    omit: tuple[str, ...] = ()
    top: int = 10
    min_risk: Risk | None = None
    weights: Weights | None = None
    weak_only: bool = False
    default_omit: bool = True
    apply_config: bool = True


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
    omit: tuple[str, ...] | list[str] | None = None,
    top: int = 10,
    min_risk: Risk | str | None = None,
    weights: Weights | None = None,
    weak_only: bool = False,
    default_omit: bool = True,
    options: Options | None = None,
) -> GapReport:
    """
    Rank uncovered production behavior in a checkout.

    ``[tool.testrisk]`` omit/include/base/changed/min-risk/weights are applied
    when *options* is omitted or ``Options.apply_config`` is true. The CLI
    resolves flags first and passes ``apply_config=False``.

    Parameters
    ----------
    root:
        Project directory (walk-up applies when this is ``"."``).
    coverage:
        Optional ``coverage.json``, ``coverage.xml``, or ``.coverage``.
    changed_only:
        Keep gaps that intersect the git change set.
    base:
        Git ref to diff against (default: ``GITHUB_BASE_REF``, then
        ``origin/main`` / ``main`` / ``HEAD``).
    files:
        Restrict ranking to these source paths or globs.
    omit:
        Skip source paths matching these globs (merged with config ``omit``).
    top:
        How many gaps to keep (``0`` means all).
    min_risk:
        Drop gaps below this risk label.
    weights:
        Override default ranking weights.
    weak_only:
        Keep gaps with no meaningful related tests (missing or ceremonial).
    default_omit:
        Skip ``__init__.py`` and ``migrations/`` unless disabled.
    options:
        If given, the other arguments are ignored (config ``omit`` still merges).

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
        omit=tuple(omit or ()),
        top=top,
        min_risk=None if min_risk is None else parse_risk(min_risk),
        weights=weights,
        weak_only=weak_only,
        default_omit=default_omit,
    )
    repo = resolve_repo_path(str(chosen.root))
    settings = load_settings(repo) if chosen.apply_config else Settings()
    files_filter = chosen.files or settings.include
    use_default_omit = chosen.default_omit and (not chosen.apply_config or settings.default_omit)
    omit_filter = _unique(
        (*(DEFAULT_OMIT if use_default_omit else ()), *settings.omit, *chosen.omit)
    )
    changed = chosen.changed_only or settings.changed
    git_base = chosen.base or settings.base
    risk_floor = chosen.min_risk or settings.min_risk
    ranking_weights = chosen.weights or settings.weights
    weak_only = chosen.weak_only or settings.weak_only

    coverage_path = find_coverage_file(
        repo,
        None if chosen.coverage is None else Path(chosen.coverage),
    )
    snapshot = load_coverage(repo, coverage_path)
    resolved_base = resolve_base(repo, git_base)
    changed_map = changed_lines(repo, resolved_base)
    inventory = iter_test_files(repo)

    gaps: list[Gap] = []
    changed_statements = 0
    changed_covered = 0
    changed_missing: list[int] = []

    for file_cov in snapshot.files:
        if is_test_path(file_cov.path):
            continue
        if omitted(file_cov.path, omit_filter):
            continue
        if not _file_matches(file_cov.path, files_filter):
            continue
        source = repo / file_cov.path
        if not source.is_file():
            continue
        rel_changed = _changed_for(file_cov.path, changed_map)
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
                weights=ranking_weights,
            )
        )

    ranked = sort_gaps(gaps)
    if changed:
        ranked = tuple(gap for gap in ranked if gap.changed_uncovered)
    if risk_floor is not None:
        ranked = tuple(gap for gap in ranked if risk_at_least(gap.risk, risk_floor))
    if weak_only:
        ranked = tuple(gap for gap in ranked if not gap.has_meaningful_tests)
    matched = len(ranked)
    peak = worst_risk([gap.risk for gap in ranked])
    weak_matched = sum(1 for gap in ranked if gap.weak_tests)
    shown = ranked[: chosen.top] if chosen.top > 0 else ranked
    totals = totals_from_gaps(ranked, shown=len(shown))
    ranked = shown

    suggested = ranked[0].suggested_test if ranked else None
    if ranked and ranked[0].existing_tests:
        suggested = ranked[0].existing_tests[0]

    changed_cov = None
    if resolved_base is not None:
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
        matched=matched,
        worst_risk=peak,
        weak_matched=weak_matched,
        totals=totals,
        changed_only=changed,
        stale_coverage=coverage_is_stale(repo, coverage_path, changed_map),
    )


def _unique(items: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _file_matches(path: Path, filters: tuple[str, ...]) -> bool:
    if not filters:
        return True
    return any(matches_glob(path, item) for item in filters)


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
    weights: Weights,
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
        if bucket.span.name == "<module>" and not unique_branches and not changed_uncovered:
            continue
        existing = related_tests(repo, rel, bucket.span.name, inventory=inventory)
        suggested = existing[0] if existing else suggested_test_path(rel, inventory=inventory)
        weak_paths, weak_reasons = _weak_related(repo, existing, bucket.span.name)
        kind = _test_kind(repo, suggested, existing, weak_paths)
        meaningful = kind is TestKind.MEANINGFUL
        value, risk, parts = score_gap(
            missing_lines=len(missing),
            missing_branches=len(unique_branches),
            complexity=bucket.span.complexity,
            changed_uncovered=len(changed_uncovered),
            has_tests=meaningful,
            weights=weights,
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
                score_parts=parts,
                weak_tests=weak_paths,
                weak_reasons=weak_reasons,
                test_kind=kind,
            )
        )
    return gaps


def _test_kind(
    repo: Path,
    suggested: Path,
    existing: tuple[Path, ...],
    weak_paths: tuple[Path, ...],
) -> TestKind:
    if existing:
        weak = set(weak_paths)
        if any(path not in weak for path in existing):
            return TestKind.MEANINGFUL
        return TestKind.WEAK
    if (repo / suggested).is_file():
        return TestKind.INDIRECT
    return TestKind.NONE


def _weak_related(
    repo: Path,
    existing: tuple[Path, ...],
    func_name: str,
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    weak_paths: list[Path] = []
    reasons: list[str] = []
    for path in existing:
        try:
            text = (repo / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        strength = inspect_test_strength(text, func_name)
        if strength.meaningful:
            continue
        weak_paths.append(path)
        reasons.extend(strength.reasons)
    return tuple(weak_paths), tuple(dict.fromkeys(reasons))
