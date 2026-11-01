"""Baseline waive / write."""

import json
from pathlib import Path

import pytest
from helpers import write_coverage_json, write_sample_project

from testrisk import analyze
from testrisk.baseline import load_baseline, write_baseline
from testrisk.errors import GapError


def test_load_line_oriented_and_json(tmp_path):
    text = tmp_path / "lines.txt"
    text.write_text("# note\ndemo/services.py::start\n\n", encoding="utf-8")
    assert load_baseline(text) == frozenset({"demo/services.py::start"})
    data = tmp_path / "base.json"
    write_baseline(data, ["b", "a", "a"])
    payload = json.loads(data.read_text(encoding="utf-8"))
    assert payload["waived"] == ["a", "b"]
    assert load_baseline(data) == frozenset({"a", "b"})


def test_load_baseline_rejects_bad_json(tmp_path):
    path = tmp_path / ".testrisk-baseline"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(GapError, match="parse"):
        load_baseline(path)


def test_analyze_waives_baseline_gaps(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9, 15, 16],
        executed_lines=list(range(1, 8)),
    )
    all_gaps = analyze(tmp_path, top=0, baseline="")
    start = next(gap for gap in all_gaps.gaps if gap.name == "ServiceManager.start")
    write_baseline(tmp_path / ".testrisk-baseline", [start.qualname])
    filtered = analyze(tmp_path, top=0)
    names = {gap.name for gap in filtered.gaps}
    assert "ServiceManager.start" not in names
    assert start.qualname in filtered.waived


def test_write_baseline_does_not_hide_current_run(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    report = analyze(tmp_path, top=0, write_baseline=True)
    assert report.gaps
    assert (tmp_path / ".testrisk-baseline").is_file()
    assert Path("demo/services.py").as_posix() in report.gaps[0].path.as_posix()
