"""Static fan-in: how many production modules import a file."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from .tests_map import iter_source_files


def fan_in_counts(root: Path) -> dict[Path, int]:
    """Map repo-relative modules to the number of production importers."""
    sources = iter_source_files(root)
    importers: dict[Path, set[Path]] = defaultdict(set)
    for rel in sources:
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8"), filename=str(rel))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for target in _imported_paths(root, rel, tree):
            if target != rel:
                importers[target].add(rel)
    return {path: len(found) for path, found in importers.items()}


def _imported_paths(root: Path, source: Path, tree: ast.AST) -> set[Path]:
    found: set[Path] = set()
    package = _package_of(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                path = _resolve_module(root, alias.name)
                if path is not None:
                    found.add(path)
        elif isinstance(node, ast.ImportFrom):
            module = _from_module(package, node)
            if module:
                path = _resolve_module(root, module)
                if path is not None:
                    found.add(path)
            for alias in node.names:
                if alias.name == "*":
                    continue
                qualified = f"{module}.{alias.name}" if module else alias.name
                path = _resolve_module(root, qualified)
                if path is not None:
                    found.add(path)
    return found


def _package_of(source: Path) -> str:
    parts = [part for part in source.parts[:-1] if part != "src"]
    return ".".join(parts)


def _from_module(package: str, node: ast.ImportFrom) -> str | None:
    if node.level <= 0:
        return node.module
    parents = package.split(".") if package else []
    drop = node.level - 1
    if drop:
        parents = parents[:-drop] if drop <= len(parents) else []
    prefix = ".".join(parents)
    if node.module and prefix:
        return f"{prefix}.{node.module}"
    return node.module or prefix or None


def _resolve_module(root: Path, module: str) -> Path | None:
    parts = [part for part in module.split(".") if part]
    if not parts:
        return None
    candidate = Path(*parts).with_suffix(".py")
    if (root / candidate).is_file():
        return candidate
    if parts[0] != "src":
        nested = Path("src", *parts).with_suffix(".py")
        if (root / nested).is_file():
            return nested
    init = Path(*parts) / "__init__.py"
    if (root / init).is_file():
        return init
    return None
