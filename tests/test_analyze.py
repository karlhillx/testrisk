"""End-to-end ranking from a synthetic project."""

import os
from pathlib import Path

from helpers import write_coverage_json, write_sample_project

import testrisk.engine as engine
from testrisk import analyze
from testrisk.models import Risk, TestKind


def test_analyze_ranks_uncovered_method_first(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9, 15, 16, 17, 18],
        executed_lines=list(range(1, 8)),
        missing_branches=[[15, 16], [16, 0]],
        line_percent=54.0,
        branch_percent=40.0,
    )
    report = analyze(tmp_path, top=10)
    assert report.coverage.line_percent == 54.0
    names = [gap.name for gap in report.gaps]
    assert "ServiceManager.start" in names
    assert "parse_config" in names
    top = report.gaps[0]
    assert top.name == "ServiceManager.start"
    assert top.kind is TestKind.INDIRECT
    assert top.risk in {Risk.HIGH, Risk.MEDIUM}
    parse = next(gap for gap in report.gaps if gap.name == "parse_config")
    assert parse.kind is TestKind.MEANINGFUL
    assert report.suggested_target == Path("tests/test_services.py")
    assert report.totals.matched >= len(report.gaps)
    assert report.totals.shown == len(report.gaps)
    assert report.totals.high + report.totals.medium + report.totals.low == report.totals.matched


def test_analyze_file_filter(tmp_path):
    write_sample_project(tmp_path)
    extra = tmp_path / "demo" / "other.py"
    extra.write_text("def unused():\n    return 1\n", encoding="utf-8")
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9],
        executed_lines=[1, 2, 3],
    )
    # second file via a hand-edited payload
    import json

    payload = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    payload["files"]["demo/other.py"] = {
        "executed_lines": [],
        "missing_lines": [2],
        "excluded_lines": [],
        "missing_branches": [],
    }
    (tmp_path / "coverage.json").write_text(json.dumps(payload), encoding="utf-8")

    report = analyze(tmp_path, files=("demo/other.py",), top=0)
    assert [gap.path.as_posix() for gap in report.gaps] == ["demo/other.py"]


def test_analyze_changed_only_filters(tmp_path, monkeypatch):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9, 15, 16],
        executed_lines=list(range(1, 8)),
    )
    monkeypatch.setattr(
        engine,
        "changed_lines",
        lambda _root, _base: {Path("demo/services.py"): frozenset({15, 16})},
    )
    monkeypatch.setattr(engine, "resolve_base", lambda _root, _base: "HEAD")
    report = analyze(tmp_path, changed_only=True, top=0)
    assert report.gaps
    assert all(gap.changed_uncovered for gap in report.gaps)
    assert report.changed is not None
    assert report.changed.statements >= 1


def test_analyze_skips_test_files(tmp_path):
    write_sample_project(tmp_path)
    import json

    payload = {
        "meta": {},
        "files": {
            "tests/test_services.py": {
                "executed_lines": [1],
                "missing_lines": [3],
                "excluded_lines": [],
                "missing_branches": [],
            }
        },
        "totals": {
            "covered_lines": 1,
            "num_statements": 2,
            "percent_covered": 50.0,
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(payload), encoding="utf-8")
    report = analyze(tmp_path)
    assert report.gaps == ()


def test_analyze_omit_skips_file(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    report = analyze(tmp_path, omit=("demo/services.py",), top=0)
    assert report.gaps == ()


def test_analyze_file_glob(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    report = analyze(tmp_path, files=("demo/**",), top=0)
    assert report.gaps
    assert all(gap.path.as_posix().startswith("demo/") for gap in report.gaps)


def test_analyze_min_risk_filters(tmp_path, monkeypatch):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9, 15, 16, 17, 18],
        executed_lines=list(range(1, 8)),
        missing_branches=[[15, 16], [16, 0]],
    )
    monkeypatch.setattr(
        engine,
        "changed_lines",
        lambda _root, _base: {Path("demo/services.py"): frozenset({15, 16, 17, 18})},
    )
    monkeypatch.setattr(engine, "resolve_base", lambda _root, _base: "HEAD")
    all_gaps = analyze(tmp_path, top=0)
    high_only = analyze(tmp_path, min_risk="HIGH", top=0)
    assert high_only.gaps
    assert all(gap.risk is Risk.HIGH for gap in high_only.gaps)
    assert len(high_only.gaps) <= len(all_gaps.gaps)


def test_analyze_config_omit(tmp_path):
    write_sample_project(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n\n[tool.testrisk]\nomit = ['demo/**']\n",
        encoding="utf-8",
    )
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    report = analyze(tmp_path, top=0)
    assert report.gaps == ()


def test_analyze_weak_related_counts_as_missing_checks(tmp_path):
    write_sample_project(tmp_path)
    (tmp_path / "tests" / "test_services.py").write_text(
        "from demo.services import ServiceManager\n\n"
        "def test_start_smoke():\n"
        "    ServiceManager().start('x')\n"
        "    assert True\n",
        encoding="utf-8",
    )
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16, 17, 18],
        executed_lines=list(range(1, 8)),
    )
    report = analyze(tmp_path, top=0)
    start = next(gap for gap in report.gaps if gap.name == "ServiceManager.start")
    assert start.has_tests is True
    assert start.has_meaningful_tests is False
    assert start.kind is TestKind.WEAK
    assert start.weak_tests
    assert start.score_parts.no_tests == 4.0


def test_analyze_weak_only_hides_meaningful(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9, 15, 16],
        executed_lines=list(range(1, 8)),
    )
    all_gaps = analyze(tmp_path, top=0)
    weak = analyze(tmp_path, weak_only=True, top=0)
    assert all_gaps.gaps
    assert all(not gap.has_meaningful_tests for gap in weak.gaps)


def test_analyze_start_without_mention_is_untested(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16, 17, 18],
        executed_lines=list(range(1, 8)),
    )
    report = analyze(tmp_path, top=0)
    start = next(gap for gap in report.gaps if gap.name == "ServiceManager.start")
    assert start.has_tests is False
    assert start.kind is TestKind.INDIRECT
    assert start.score_parts.no_tests == 4.0


def test_analyze_none_when_suggested_missing(tmp_path):
    write_sample_project(tmp_path)
    (tmp_path / "tests" / "test_services.py").unlink()
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16, 17, 18],
        executed_lines=list(range(1, 8)),
    )
    report = analyze(tmp_path, top=0)
    start = next(gap for gap in report.gaps if gap.name == "ServiceManager.start")
    assert start.kind is TestKind.NONE
    assert start.score_parts.no_tests == 4.0


def test_analyze_default_omit_skips_init_and_migrations(tmp_path):
    write_sample_project(tmp_path)
    (tmp_path / "demo" / "__init__.py").write_text(
        "def leftover():\n    return 1\n",
        encoding="utf-8",
    )
    migrations = tmp_path / "demo" / "migrations"
    migrations.mkdir()
    (migrations / "0001_init.py").write_text("def apply():\n    return 1\n", encoding="utf-8")
    write_coverage_json(tmp_path, missing_lines=[15], executed_lines=[1])
    import json

    payload = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    payload["files"]["demo/__init__.py"] = {
        "executed_lines": [],
        "missing_lines": [2],
        "excluded_lines": [],
        "missing_branches": [],
    }
    payload["files"]["demo/migrations/0001_init.py"] = {
        "executed_lines": [],
        "missing_lines": [2],
        "excluded_lines": [],
        "missing_branches": [],
    }
    (tmp_path / "coverage.json").write_text(json.dumps(payload), encoding="utf-8")

    hidden = analyze(tmp_path, top=0)
    hidden_paths = {gap.path.as_posix() for gap in hidden.gaps}
    assert "demo/__init__.py" not in hidden_paths
    assert "demo/migrations/0001_init.py" not in hidden_paths

    shown = analyze(tmp_path, top=0, default_omit=False)
    shown_paths = {gap.path.as_posix() for gap in shown.gaps}
    assert "demo/__init__.py" in shown_paths
    assert "demo/migrations/0001_init.py" in shown_paths


def test_analyze_skips_quiet_module_gaps(tmp_path):
    write_sample_project(tmp_path)
    (tmp_path / "demo" / "const.py").write_text("VALUE = 1\nFLAG = 2\n", encoding="utf-8")
    write_coverage_json(
        tmp_path,
        filename="demo/const.py",
        missing_lines=[1, 2],
        executed_lines=[],
    )
    report = analyze(tmp_path, top=0)
    assert report.gaps == ()


def test_analyze_keeps_module_gap_with_branch(tmp_path):
    write_sample_project(tmp_path)
    (tmp_path / "demo" / "boot.py").write_text(
        "if True:\n    X = 1\nelse:\n    X = 2\n",
        encoding="utf-8",
    )
    write_coverage_json(
        tmp_path,
        filename="demo/boot.py",
        missing_lines=[4],
        executed_lines=[1, 2],
        missing_branches=[[1, 4]],
    )
    report = analyze(tmp_path, top=0)
    assert any(gap.name == "<module>" and gap.missing_branches for gap in report.gaps)


def test_analyze_keeps_changed_module_gap(tmp_path, monkeypatch):
    write_sample_project(tmp_path)
    (tmp_path / "demo" / "const.py").write_text("VALUE = 1\n", encoding="utf-8")
    write_coverage_json(
        tmp_path,
        filename="demo/const.py",
        missing_lines=[1],
        executed_lines=[],
    )
    monkeypatch.setattr(
        engine,
        "changed_lines",
        lambda _root, _base: {Path("demo/const.py"): frozenset({1})},
    )
    monkeypatch.setattr(engine, "resolve_base", lambda _root, _base: "HEAD")
    report = analyze(tmp_path, top=0)
    module = next(gap for gap in report.gaps if gap.name == "<module>")
    assert module.changed_uncovered == (1,)


def test_analyze_marks_stale_coverage(tmp_path, monkeypatch):
    write_sample_project(tmp_path)
    coverage = write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    source = tmp_path / "demo" / "services.py"
    os.utime(coverage, (1_000_000, 1_000_000))
    os.utime(source, (2_000_000, 2_000_000))
    monkeypatch.setattr(
        engine,
        "changed_lines",
        lambda _root, _base: {Path("demo/services.py"): frozenset({15})},
    )
    monkeypatch.setattr(engine, "resolve_base", lambda _root, _base: "HEAD")
    report = analyze(tmp_path, top=0)
    assert report.stale_coverage is True
    assert report.changed_only is False


def test_analyze_coverage_not_stale_when_newer(tmp_path, monkeypatch):
    write_sample_project(tmp_path)
    coverage = write_coverage_json(
        tmp_path,
        missing_lines=[15],
        executed_lines=[1],
    )
    source = tmp_path / "demo" / "services.py"
    os.utime(source, (1_000_000, 1_000_000))
    os.utime(coverage, (2_000_000, 2_000_000))
    monkeypatch.setattr(
        engine,
        "changed_lines",
        lambda _root, _base: {Path("demo/services.py"): frozenset({15})},
    )
    monkeypatch.setattr(engine, "resolve_base", lambda _root, _base: "HEAD")
    report = analyze(tmp_path, top=0)
    assert report.stale_coverage is False
