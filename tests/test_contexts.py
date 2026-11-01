"""Coverage.py test-context mapping."""

from pathlib import Path

from helpers import write_coverage_json, write_sample_project

from testrisk import analyze
from testrisk.contexts import executed_by, nodeid_to_path, normalize_context, parse_contexts
from testrisk.models import FileCoverage, FunctionSpan, TestKind


def test_normalize_and_nodeid():
    assert normalize_context("") is None
    assert normalize_context("  tests/test_foo.py::test_bar|run  ") == "tests/test_foo.py::test_bar"
    assert nodeid_to_path("tests/test_foo.py::Test::test_bar") == Path("tests/test_foo.py")
    assert nodeid_to_path("not-a-file") is None


def test_parse_contexts_skips_empty():
    assert parse_contexts({"1": [""], "2": ["tests/test_a.py::test_a"]}) == {
        2: ("tests/test_a.py::test_a",)
    }


def test_executed_by_ignores_missing_lines():
    span = FunctionSpan(path=Path("demo/services.py"), name="start", start=10, end=20, complexity=2)
    file_cov = FileCoverage(
        path=Path("demo/services.py"),
        executed_lines=frozenset({12, 15}),
        missing_lines=frozenset({15, 16}),
        excluded_lines=frozenset(),
        contexts={
            12: ("tests/test_services.py::test_start",),
            15: ("tests/test_other.py::test_other",),
        },
    )
    assert executed_by(file_cov, span) == ("tests/test_services.py::test_start",)


def test_analyze_uses_contexts_as_meaningful(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[16, 17, 18],
        executed_lines=list(range(1, 16)),
        contexts={
            str(line): ["tests/test_services.py::test_parse_config_empty"] for line in range(9, 16)
        },
    )
    report = analyze(tmp_path, top=0)
    start = next(gap for gap in report.gaps if gap.name == "ServiceManager.start")
    assert report.has_contexts is True
    assert start.executed_by
    assert start.kind is TestKind.MEANINGFUL
    assert start.score_parts.no_tests == 0.0
