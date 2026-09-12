"""End-to-end ranking from a synthetic project."""

from pathlib import Path

from helpers import write_coverage_json, write_sample_project

import testgap.engine as engine
from testgap import analyze
from testgap.models import Risk


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
    assert top.risk in {Risk.HIGH, Risk.MEDIUM}
    assert report.suggested_target == Path("tests/test_services.py")


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
