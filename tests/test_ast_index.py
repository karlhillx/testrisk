"""Function spans and complexity."""

from pathlib import Path

from helpers import SAMPLE_SOURCE

from testrisk.ast_index import index_file, innermost, module_complexity


def test_index_names_methods_and_functions():
    spans = index_file(Path("demo/services.py"), SAMPLE_SOURCE)
    names = {span.name: span for span in spans}
    assert "parse_config" in names
    assert "ServiceManager.start" in names
    assert names["parse_config"].complexity >= 4
    assert names["ServiceManager.start"].complexity >= 3


def test_innermost_prefers_nested_function():
    source = (
        "def outer():\n    def inner(x):\n        if x:\n            return x\n    return inner\n"
    )
    spans = index_file(Path("mod.py"), source)
    inner = innermost(3, spans)
    assert inner is not None
    assert inner.name == "outer.inner"


def test_module_complexity_ignores_nested_defs():
    source = "x = 1\nif x:\n    def helper():\n        if True:\n            return 1\n"
    assert module_complexity(Path("mod.py"), source) == 2


def test_syntax_error_returns_empty():
    assert index_file(Path("bad.py"), "def (\n") == ()
