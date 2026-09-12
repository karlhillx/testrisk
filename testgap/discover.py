"""Locate a repo root and coverage artifacts."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import GapError

COVERAGE_CANDIDATES = (
    "coverage.json",
    "coverage.xml",
    ".coverage",
)

_ROOT_MARKERS = (
    "pyproject.toml",
    ".git",
    "setup.cfg",
    "setup.py",
)


def find_repo_root(start: Path) -> Path | None:
    """Walk *start* and its parents for a Python / git project marker."""
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if any((candidate / marker).exists() for marker in _ROOT_MARKERS):
            return candidate
    return None


def resolve_repo_path(repo_arg: str) -> Path:
    """
    Resolve ``--repo``.

    When the argument is the default ``.`` and the current directory has no
    project marker, walk parents. An explicit path is used as-is.
    """
    path = Path(repo_arg).expanduser().resolve(strict=False)
    if repo_arg in (".", "") and not _looks_like_root(path):
        found = find_repo_root(path)
        if found is not None:
            return found
    return path


def _looks_like_root(path: Path) -> bool:
    return any((path / marker).exists() for marker in _ROOT_MARKERS)


def find_coverage_file(root: Path, explicit: Path | None = None) -> Path:
    """Return the coverage artifact to load, or raise ``GapError``."""
    if explicit is not None:
        path = explicit.expanduser()
        path = path.resolve() if path.is_absolute() else (root / path).resolve()
        if path.is_dir():
            found = _first_candidate(path)
            if found is None:
                raise GapError(f"No coverage data found in {path}")
            return found
        if not path.is_file():
            raise GapError(f"Coverage file not found: {path}")
        return path

    found = _first_candidate(root)
    if found is not None:
        return found
    raise GapError(
        "No coverage data found.\n\n"
        "  Looked for: coverage.json, coverage.xml, .coverage\n\n"
        "  Generate it with:\n"
        "    pytest --cov --cov-report=json\n"
        "    # or\n"
        "    coverage run -m pytest && coverage json"
    )


def _first_candidate(directory: Path) -> Path | None:
    for name in COVERAGE_CANDIDATES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def relativize(path: Path, root: Path) -> Path:
    """Best-effort path relative to *root*; keep absolute if outside."""
    resolved = path if path.is_absolute() else (root / path)
    try:
        return resolved.resolve().relative_to(root.resolve())
    except ValueError:
        return Path(path)


def path_key(path: Path) -> str:
    """Stable comparison key for repo-relative paths (case-fold on Windows)."""
    posix = path.as_posix().replace("\\", "/")
    return posix.casefold() if os.name == "nt" else posix


def same_relpath(left: Path, right: Path) -> bool:
    """True if two repo-relative paths refer to the same file."""
    left_key = path_key(left)
    right_key = path_key(right)
    if left_key == right_key:
        return True
    return left_key.endswith("/" + right_key) or right_key.endswith("/" + left_key)


def matches_filter(path: Path, needle: Path) -> bool:
    """True if *path* is *needle* or ends with it (``--file``)."""
    posix = path_key(path)
    key = path_key(needle)
    if posix == key or posix.endswith("/" + key):
        return True
    return path_key(Path(path.name)) == key
