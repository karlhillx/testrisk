"""Map coverage.py test contexts onto functions."""

from __future__ import annotations

from pathlib import Path

from .models import FileCoverage, FunctionSpan


def normalize_context(raw: str) -> str | None:
    """Strip empty and coverage.py ``|run`` / ``|setup`` suffixes."""
    text = raw.strip()
    if not text:
        return None
    if "|" in text:
        text = text.split("|", 1)[0].strip()
    return text or None


def nodeid_to_path(nodeid: str) -> Path | None:
    """``tests/test_foo.py::test_bar`` → ``tests/test_foo.py``."""
    head = nodeid.replace("\\", "/").split("::", 1)[0]
    if head.endswith(".py"):
        return Path(head)
    return None


def parse_contexts(raw: object) -> dict[int, tuple[str, ...]]:
    """Normalize a coverage.py ``contexts`` object."""
    if not isinstance(raw, dict):
        return {}
    mapped: dict[int, tuple[str, ...]] = {}
    for key, values in raw.items():
        try:
            line = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(values, list):
            continue
        names = tuple(
            dict.fromkeys(name for item in values if (name := normalize_context(str(item))))
        )
        if names:
            mapped[line] = names
    return mapped


def executed_by(file_cov: FileCoverage, span: FunctionSpan) -> tuple[str, ...]:
    """Tests that executed any line in *span* (usually not the missing ones)."""
    if not file_cov.has_contexts:
        return ()
    names: list[str] = []
    for line, contexts in file_cov.contexts.items():
        if line < span.start or line > span.end:
            continue
        if line in file_cov.missing_lines:
            continue
        names.extend(contexts)
    return tuple(dict.fromkeys(names))


def paths_for_contexts(nodeids: tuple[str, ...], *, root: Path) -> tuple[Path, ...]:
    """Repo-relative test files that still exist for these nodeids."""
    found: list[Path] = []
    for nodeid in nodeids:
        path = nodeid_to_path(nodeid)
        if path is None:
            continue
        if (root / path).is_file() and path not in found:
            found.append(path)
    return tuple(found)
