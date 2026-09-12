"""Guess which test files already cover a source function."""

from __future__ import annotations

import os
import re
from pathlib import Path

_TEST_NAME = re.compile(r"(^test_.*\.py$|.*_test\.py$)")
_TEST_DIRS = frozenset({"tests", "test"})
_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    ".env",
    "site-packages",
    "node_modules",
    "__pycache__",
    "__pypackages__",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".ty_cache",
    ".direnv",
    "dist",
    "build",
    "htmlcov",
    "wheels",
    ".eggs",
}


def is_test_path(path: Path) -> bool:
    """True for test modules we should not rank as production gaps."""
    if path.name == "conftest.py" or _TEST_NAME.match(path.name):
        return True
    return any(part in _TEST_DIRS for part in path.parts)


def suggested_test_path(source: Path) -> Path:
    """Conventional destination for new tests of *source*."""
    return Path("tests") / f"test_{source.stem}.py"


def related_tests(
    root: Path,
    source: Path,
    func_name: str,
    *,
    inventory: tuple[Path, ...] | None = None,
) -> tuple[Path, ...]:
    """Test files that mention *func_name* or the source module stem."""
    stem = source.stem
    short = func_name.rsplit(".", 1)[-1]
    name_re = re.compile(rf"\b{re.escape(short)}\b")
    stem_re = re.compile(rf"\b{re.escape(stem)}\b")
    hits: list[Path] = []
    preferred = suggested_test_path(source)
    for test in inventory if inventory is not None else iter_test_files(root):
        try:
            text = (root / test).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if name_re.search(text) or stem_re.search(text) or test == preferred:
            hits.append(test)
    hits.sort(key=lambda path: (path != preferred, path.as_posix()))
    return tuple(hits)


def iter_test_files(root: Path) -> tuple[Path, ...]:
    """Repo-relative test modules, skipping virtualenvs and caches."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if not _skip_dir(name)]
        current = Path(dirpath)
        for name in filenames:
            if not name.endswith(".py"):
                continue
            rel = (current / name).relative_to(root)
            if is_test_path(rel):
                found.append(rel)
    return tuple(sorted(found, key=lambda item: item.as_posix()))


def _skip_dir(name: str) -> bool:
    return name in _SKIP_DIRS or name.endswith(".egg-info")
