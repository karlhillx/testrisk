"""Map source files to function/method spans and cyclomatic-ish complexity."""

from __future__ import annotations

import ast
from pathlib import Path

from .models import FunctionSpan

_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def index_file(path: Path, source: str | None = None) -> tuple[FunctionSpan, ...]:
    """Return functions/methods in *path*, innermost-friendly for line mapping."""
    try:
        text = path.read_text(encoding="utf-8") if source is None else source
    except (OSError, UnicodeDecodeError):
        return ()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return ()
    spans: list[FunctionSpan] = []
    _visit(tree.body, path, (), spans)
    return tuple(spans)


def innermost(
    line: int,
    spans: tuple[FunctionSpan, ...] | list[FunctionSpan],
) -> FunctionSpan | None:
    """The tightest function/method containing *line*, if any."""
    containing = [span for span in spans if span.start <= line <= span.end]
    if not containing:
        return None
    return min(containing, key=lambda span: (span.end - span.start, -span.start))


def module_complexity(path: Path, source: str | None = None) -> int:
    """Complexity of module-level control flow only (nested defs skipped)."""
    try:
        text = path.read_text(encoding="utf-8") if source is None else source
    except (OSError, UnicodeDecodeError):
        return 1
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return 1
    return _complexity(tree)


def _visit(
    nodes: list[ast.stmt],
    path: Path,
    prefix: tuple[str, ...],
    spans: list[FunctionSpan],
) -> None:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = ".".join((*prefix, node.name))
            start = node.lineno
            end = node.end_lineno or node.lineno
            spans.append(
                FunctionSpan(
                    path=path,
                    name=name,
                    start=start,
                    end=end,
                    complexity=_complexity(node),
                )
            )
            _visit(node.body, path, (*prefix, node.name), spans)
        elif isinstance(node, ast.ClassDef):
            _visit(node.body, path, (*prefix, node.name), spans)


def _complexity(node: ast.AST) -> int:
    score = 1
    for child in _iter_local(node):
        match child:
            case (
                ast.If()
                | ast.For()
                | ast.AsyncFor()
                | ast.While()
                | ast.IfExp()
                | ast.Assert()
                | ast.ExceptHandler()
            ):
                score += 1
            case ast.With() | ast.AsyncWith():
                score += 1
            case ast.BoolOp():
                score += max(0, len(child.values) - 1)
            case ast.comprehension():
                score += 1 + len(child.ifs)
            case ast.Match():
                score += len(child.cases)
    return score


def _iter_local(node: ast.AST):
    """Walk *node*, skipping nested functions and classes."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTED):
            continue
        yield child
        yield from _iter_local(child)
