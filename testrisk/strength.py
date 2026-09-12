"""Static checks for ceremonial related tests — not mutation testing."""

from __future__ import annotations

import ast
from dataclasses import dataclass

NO_ASSERTIONS = "no_assertions"
TAUTOLOGY = "tautological_assertions"
NEVER_CALLED = "never_called"

REASON_LABELS = {
    NO_ASSERTIONS: "no assertions",
    TAUTOLOGY: "only tautological assertions",
    NEVER_CALLED: "never calls the function",
}

_STRONG_HELPERS = frozenset(
    {
        "assertAlmostEqual",
        "assertCountEqual",
        "assertDictEqual",
        "assertEqual",
        "assertEquals",
        "assertGreater",
        "assertGreaterEqual",
        "assertIn",
        "assertIs",
        "assertIsInstance",
        "assertLess",
        "assertLessEqual",
        "assertListEqual",
        "assertMultiLineEqual",
        "assertNotEqual",
        "assertNotIn",
        "assertRaises",
        "assertRaisesRegex",
        "assertRegex",
        "assertSequenceEqual",
        "assertSetEqual",
        "assertTupleEqual",
        "assertWarns",
        "deprecated_call",
        "fail",
        "raises",
        "warns",
    }
)
_WEAK_HELPERS = frozenset(
    {
        "assertFalse",
        "assertIsNone",
        "assertIsNotNone",
        "assertTrue",
    }
)


@dataclass(frozen=True)
class TestStrength:
    """Whether a related test file can fail if the function is wrong."""

    meaningful: bool
    reasons: tuple[str, ...]

    def labels(self) -> tuple[str, ...]:
        return tuple(REASON_LABELS[reason] for reason in self.reasons if reason in REASON_LABELS)


def inspect_test_strength(source: str, func_name: str) -> TestStrength:
    """
    Classify a related test module for *func_name*.

    Conservative: unreadable files are treated as meaningful so we do not
    invent a quality score from a parse error.
    """
    short = func_name.rsplit(".", 1)[-1]
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return TestStrength(meaningful=True, reasons=())

    focused = [node for node in _test_nodes(tree) if _mentions(node, short)]
    if not focused:
        # Import-only mention: the file is related but nothing exercises the function.
        called = _calls_function(tree, short)
        if called:
            return _classify(_collect_checks(tree), called=True)
        return TestStrength(meaningful=False, reasons=(NEVER_CALLED, NO_ASSERTIONS))

    checks: list[bool] = []
    called = False
    for node in focused:
        checks.extend(_collect_checks(node))
        called = called or _calls_function(node, short)
    return _classify(checks, called=called)


def _classify(checks: list[bool], *, called: bool) -> TestStrength:
    if any(checks):
        return TestStrength(meaningful=True, reasons=())
    reasons: list[str] = []
    if not checks:
        reasons.append(NO_ASSERTIONS)
    else:
        reasons.append(TAUTOLOGY)
    if not called:
        reasons.append(NEVER_CALLED)
    return TestStrength(meaningful=False, reasons=tuple(reasons))


def _test_nodes(tree: ast.AST) -> list[ast.stmt]:
    found: list[ast.stmt] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_test_fn(node.name):
            found.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_test_fn(
                    child.name
                ):
                    found.append(child)
    return found


def _is_test_fn(name: str) -> bool:
    return name.startswith("test") or name.startswith("Test")


def _mentions(node: ast.AST, short: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == short:
            return True
        if isinstance(child, ast.Attribute) and child.attr == short:
            return True
    return False


def _calls_function(node: ast.AST, short: str) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name) and func.id == short:
            return True
        if isinstance(func, ast.Attribute) and func.attr == short:
            return True
    return False


def _collect_checks(node: ast.AST) -> list[bool]:
    """Each entry is True when the check looks like it can fail meaningfully."""
    checks: list[bool] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            checks.append(not _weak_assert(child))
        elif isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name in _STRONG_HELPERS:
                checks.append(True)
            elif name in _WEAK_HELPERS:
                checks.append(not _weak_helper_args(child))
    return checks


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _weak_assert(node: ast.Assert) -> bool:
    return _weak_predicate(node.test)


def _weak_helper_args(call: ast.Call) -> bool:
    if not call.args:
        return True
    return _weak_predicate(call.args[0])


def _weak_predicate(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Constant) and expr.value is True:
        return True
    if isinstance(expr, ast.Name):
        return True
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        return isinstance(expr.operand, (ast.Name, ast.Constant))
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1:
        op = expr.ops[0]
        other = expr.comparators[0]
        if isinstance(op, ast.IsNot) and _is_none(other):
            return True
        if isinstance(op, ast.Is) and _is_none(expr.left) and isinstance(other, ast.Name):
            return True
        if isinstance(op, ast.NotEq) and _is_none(other):
            return True
    return False


def _is_none(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and expr.value is None
