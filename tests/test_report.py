"""Text, JSON, and prompt renderers."""

import json
from pathlib import Path

from testgap.models import (
    BranchGap,
    ChangedCoverage,
    CoverageSnapshot,
    FileCoverage,
    Gap,
    GapReport,
    Risk,
)
from testgap.report import build_prompt, render_json, render_text


def _report(gaps: tuple[Gap, ...]) -> GapReport:
    snap = CoverageSnapshot(
        files=(
            FileCoverage(
                path=Path("demo/services.py"),
                executed_lines=frozenset({1, 2}),
                missing_lines=frozenset({8, 9}),
                excluded_lines=frozenset(),
            ),
        ),
        source=Path("coverage.json"),
        line_percent=91.7,
        branch_percent=84.2,
        covered_lines=11,
        statements=12,
        covered_branches=5,
        branches=6,
    )
    return GapReport(
        version="1.0.0",
        root=Path("."),
        coverage=snap,
        gaps=gaps,
        changed=ChangedCoverage(percent=94.1, covered=16, statements=17, missing=(18,)),
        suggested_target=Path("tests/test_services.py"),
    )


def test_render_text_matches_shape(capsys):
    gap = Gap(
        path=Path("demo/services.py"),
        name="ServiceManager.start",
        missing_lines=(15, 16, 17),
        missing_branches=(BranchGap(15, 16), BranchGap(16, 0)),
        complexity=11,
        changed_uncovered=(),
        has_tests=True,
        existing_tests=(Path("tests/test_services.py"),),
        suggested_test=Path("tests/test_services.py"),
        score=20.0,
        risk=Risk.HIGH,
    )
    render_text(_report((gap,)))
    out = capsys.readouterr().out
    assert "test-gap 1.0.0" in out
    assert "Coverage   91.7%" in out
    assert "Branch     84.2%" in out
    assert "demo/services.py::ServiceManager.start" in out
    assert "Missing: 15-17" in out
    assert "Branches: 2 uncovered" in out
    assert "Complexity: 11" in out
    assert "Risk: HIGH" in out
    assert "94.1% covered" in out
    assert "1 uncovered executable line" in out
    assert "tests/test_services.py" in out


def test_prompt_is_actionable():
    gap = Gap(
        path=Path("src/foo.py"),
        name="parse_config",
        missing_lines=(44, 45, 46, 47, 48, 57),
        missing_branches=(BranchGap(46, 0), BranchGap(57, -1)),
        complexity=6,
        changed_uncovered=(),
        has_tests=True,
        existing_tests=(Path("tests/test_foo.py"),),
        suggested_test=Path("tests/test_foo.py"),
        score=12.0,
        risk=Risk.MEDIUM,
    )
    text = build_prompt(_report((gap,)))
    assert "Write focused unit tests" in text
    assert "src/foo.py::parse_config" in text
    assert "44-48, 57" in text
    assert "line 46: false branch" in text
    assert "line 57: exception/exit branch" in text
    assert "tests/test_foo.py" in text
    assert "Do not modify production code" in text


def test_render_json_includes_prompt(capsys):
    render_json(_report(()), prompt=True)
    data = json.loads(capsys.readouterr().out)
    assert "prompt" in data
    assert data["coverage"]["percent"] == 91.7
    assert data["gaps"] == []
