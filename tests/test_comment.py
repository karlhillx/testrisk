"""PR comment markdown and GitHub helpers."""

import json
from pathlib import Path

from testrisk.comment import MARKER, _pr_number, render_markdown
from testrisk.models import (
    ChangedCoverage,
    CoverageSnapshot,
    FileCoverage,
    Gap,
    GapReport,
    Risk,
    totals_from_gaps,
)


def _report(gaps: tuple[Gap, ...] = ()) -> GapReport:
    snap = CoverageSnapshot(
        files=(
            FileCoverage(
                path=Path("demo/services.py"),
                executed_lines=frozenset({1}),
                missing_lines=frozenset({15}),
                excluded_lines=frozenset(),
            ),
        ),
        source=Path("coverage.json"),
        line_percent=91.0,
        branch_percent=None,
        covered_lines=10,
        statements=11,
        covered_branches=None,
        branches=None,
    )
    return GapReport(
        version="1.1.0",
        root=Path("."),
        coverage=snap,
        gaps=gaps,
        changed=ChangedCoverage(percent=90.0, covered=9, statements=10),
        suggested_target=Path("tests/test_services.py"),
        totals=totals_from_gaps(gaps),
    )


def test_render_markdown_table():
    gap = Gap(
        path=Path("demo/services.py"),
        name="start",
        missing_lines=(15,),
        missing_branches=(),
        complexity=2,
        changed_uncovered=(),
        has_tests=False,
        existing_tests=(),
        suggested_test=Path("tests/test_services.py"),
        score=5.0,
        risk=Risk.HIGH,
    )
    text = render_markdown(_report((gap,)))
    assert MARKER in text
    assert "demo/services.py::start" in text
    assert "HIGH" in text


def test_pr_number_from_event(tmp_path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 17}}), encoding="utf-8")
    assert _pr_number(event) == 17
    event.write_text("{}", encoding="utf-8")
    assert _pr_number(event) is None
