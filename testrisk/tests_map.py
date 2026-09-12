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
# Short / generic names that appear in many files; require a second signal.
_COMMON_NAMES = frozenset(
    {
        "add",
        "apply",
        "call",
        "clear",
        "close",
        "config",
        "create",
        "data",
        "delete",
        "format",
        "get",
        "handle",
        "helper",
        "init",
        "item",
        "list",
        "load",
        "main",
        "name",
        "open",
        "parse",
        "process",
        "read",
        "remove",
        "reset",
        "run",
        "save",
        "set",
        "setup",
        "start",
        "stop",
        "teardown",
        "test",
        "update",
        "util",
        "value",
        "write",
    }
)


def is_test_path(path: Path) -> bool:
    """True for test modules we should not rank as production gaps."""
    if path.name == "conftest.py" or _TEST_NAME.match(path.name):
        return True
    return any(part in _TEST_DIRS for part in path.parts)


def suggested_test_path(
    source: Path,
    inventory: tuple[Path, ...] | None = None,
) -> Path:
    """
    Conventional destination for new tests of *source*.

    Prefers an existing ``test_<stem>.py``. Otherwise uses a nested path for
    ``src/`` trees and packages deeper than one level.
    """
    stem = source.stem
    flat = Path("tests") / f"test_{stem}.py"
    nested = _nested_test_path(source)
    if inventory is not None:
        if flat in inventory:
            return flat
        if nested in inventory:
            return nested
        for path in inventory:
            if path.name == f"test_{stem}.py":
                return path
    if _use_nested_suggestion(source):
        return nested
    return flat


def _nested_test_path(source: Path) -> Path:
    parts = [part for part in source.parts if part != "src"]
    if not parts:
        return Path("tests") / "test_module.py"
    *dirs, name = parts
    return Path("tests", *dirs) / f"test_{Path(name).stem}.py"


def _use_nested_suggestion(source: Path) -> bool:
    parents = [part for part in source.parts[:-1] if part != "src"]
    if source.parts and source.parts[0] == "src" and parents:
        return True
    return len(parents) >= 2


def related_tests(
    root: Path,
    source: Path,
    func_name: str,
    *,
    inventory: tuple[Path, ...] | None = None,
) -> tuple[Path, ...]:
    """
    Test files that mention *func_name*.

    A conventional ``tests/test_<stem>.py`` is not treated as coverage by
    existence alone. Common short names also need the module stem or class.
    """
    stem = source.stem
    parts = func_name.split(".")
    short = parts[-1]
    class_name = parts[0] if len(parts) > 1 else None
    name_re = re.compile(rf"\b{re.escape(short)}\b")
    stem_re = re.compile(rf"\b{re.escape(stem)}\b")
    class_re = re.compile(rf"\b{re.escape(class_name)}\b") if class_name else None
    preferred = suggested_test_path(source, inventory=inventory)
    hits: list[Path] = []
    for test in inventory if inventory is not None else iter_test_files(root):
        try:
            text = (root / test).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not name_re.search(text):
            continue
        if _ambiguous_name(short) and not (
            stem_re.search(text) or (class_re is not None and class_re.search(text))
        ):
            continue
        hits.append(test)
    hits.sort(key=lambda path: (path != preferred, path.as_posix()))
    return tuple(hits)


def _ambiguous_name(short: str) -> bool:
    if short.lower() in _COMMON_NAMES:
        return True
    if "_" in short:
        return False
    return len(short) < 8


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
