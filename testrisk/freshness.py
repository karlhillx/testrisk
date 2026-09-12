"""Detect coverage artifacts that predate the files you just changed."""

from __future__ import annotations

from pathlib import Path

from .gitdiff import dirty_python_files

_SLACK_SECONDS = 1.0


def files_for_freshness(
    root: Path,
    changed: dict[Path, frozenset[int]],
) -> dict[Path, frozenset[int]]:
    """Changed lines plus dirty working-tree Python files."""
    mapping = dict(changed)
    for path in dirty_python_files(root):
        mapping.setdefault(path, frozenset())
    return mapping


def stale_sources(
    root: Path,
    coverage: Path,
    changed: dict[Path, frozenset[int]],
) -> tuple[Path, ...]:
    """Changed or dirty Python files newer than *coverage*, if any."""
    try:
        cov_mtime = coverage.stat().st_mtime
    except OSError:
        return ()
    stale: list[Path] = []
    for rel in files_for_freshness(root, changed):
        if rel.suffix != ".py":
            continue
        path = rel if rel.is_absolute() else root / rel
        if path.resolve() == coverage.resolve():
            continue
        try:
            if not path.is_file():
                continue
            source_mtime = path.stat().st_mtime
        except OSError:
            continue
        if source_mtime > cov_mtime + _SLACK_SECONDS:
            stale.append(rel if not rel.is_absolute() else Path(path.name))
    return tuple(sorted(stale, key=lambda item: item.as_posix()))


def coverage_is_stale(
    root: Path,
    coverage: Path,
    changed: dict[Path, frozenset[int]],
) -> bool:
    return bool(stale_sources(root, coverage, changed))
