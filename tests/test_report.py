"""Text, JSON, and prompt renderers."""

import json
from pathlib import Path

from testrisk.models import (
    BranchGap,
    ChangedCoverage,
    CoverageSnapshot,
    FileCoverage,
    Gap,
    GapReport,
    Risk,
    ScoreParts,
    TestKind,
    totals_from_gaps,
)
from testrisk.report import build_prompt, render_json, render_text, source_excerpt


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
        version="1.1.0",
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
        weak_tests=(Path("tests/test_services.py"),),
        weak_reasons=("no_assertions",),
    )
    render_text(_report((gap,)))
    out = capsys.readouterr().out
    assert "testrisk 1.1.0" in out
    assert "91.7%" in out
    assert "Branch 84.2%" in out
    assert "demo/services.py::ServiceManager.start" in out
    assert "15-17" in out
    assert "2 branches" in out
    assert "HIGH" in out
    assert "20.0" in out
    assert "tests/test_services.py" in out
    assert "no assertions" in out
    assert "94.1% covered" in out
    assert "1 uncovered line" in out
    assert "1. demo/services.py::ServiceManager.start" in out
    assert "risk" in out
    assert "Shown" in out
    assert "1 HIGH" in out
    assert "1 weak" in out
    assert "Hint" in out
    assert "Start with the top HIGH gap." in out


def test_render_text_explain(capsys):
    gap = Gap(
        path=Path("demo/services.py"),
        name="start",
        missing_lines=(15, 16),
        missing_branches=(),
        complexity=3,
        changed_uncovered=(15,),
        has_tests=False,
        existing_tests=(),
        suggested_test=Path("tests/test_services.py"),
        score=10.5,
        risk=Risk.MEDIUM,
        score_parts=ScoreParts(
            missing_lines=2.0,
            missing_branches=0.0,
            complexity=1.5,
            changed_uncovered=3.0,
            no_tests=4.0,
        ),
    )
    render_text(_report((gap,)), explain=True)
    out = capsys.readouterr().out
    assert "changed" in out
    assert "15" in out
    assert "lines 2.0" in out
    assert "changed 3.0" in out
    assert "no tests 4.0" in out
    assert "none → tests/test_services.py" in out


def test_render_text_indirect_label(capsys):
    gap = Gap(
        path=Path("demo/services.py"),
        name="ServiceManager.start",
        missing_lines=(15, 16),
        missing_branches=(),
        complexity=4,
        changed_uncovered=(),
        has_tests=False,
        existing_tests=(),
        suggested_test=Path("tests/test_services.py"),
        score=8.0,
        risk=Risk.MEDIUM,
        test_kind=TestKind.INDIRECT,
    )
    render_text(_report((gap,)))
    out = capsys.readouterr().out
    assert "indirect → tests/test_services.py" in out
    assert "1 indirect" in out
    assert "none →" not in out


def test_render_text_separates_gaps(capsys):
    first = Gap(
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
        risk=Risk.LOW,
    )
    second = Gap(
        path=Path("demo/services.py"),
        name="parse_config",
        missing_lines=(8,),
        missing_branches=(),
        complexity=2,
        changed_uncovered=(),
        has_tests=True,
        existing_tests=(Path("tests/test_services.py"),),
        suggested_test=Path("tests/test_services.py"),
        score=3.0,
        risk=Risk.LOW,
    )
    render_text(_report((first, second)))
    out = capsys.readouterr().out
    assert "1. demo/services.py::start" in out
    assert "2. demo/services.py::parse_config" in out
    assert "-" * 20 in out
    first_at = out.index("1. demo/services.py::start")
    rule_at = out.index("-" * 20)
    second_at = out.index("2. demo/services.py::parse_config")
    assert first_at < rule_at < second_at


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
    assert "Score: 12.0" in text


def test_prompt_notes_existing_file_without_mention(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("def test_other():\n    pass\n", encoding="utf-8")
    gap = Gap(
        path=Path("src/foo.py"),
        name="parse_config",
        missing_lines=(44,),
        missing_branches=(),
        complexity=2,
        changed_uncovered=(),
        has_tests=False,
        existing_tests=(),
        suggested_test=Path("tests/test_foo.py"),
        score=3.0,
        risk=Risk.LOW,
    )
    report = _report((gap,))
    report = GapReport(
        version=report.version,
        root=tmp_path,
        coverage=report.coverage,
        gaps=report.gaps,
        changed=report.changed,
        suggested_target=report.suggested_target,
    )
    text = build_prompt(report)
    assert "tests/test_foo.py (no mention of this function yet)" in text


def test_source_excerpt_includes_uncovered_lines(tmp_path):
    source = tmp_path / "demo"
    source.mkdir()
    (source / "services.py").write_text(
        "def start(name):\n    if not name:\n        raise ValueError('empty')\n    return True\n",
        encoding="utf-8",
    )
    gap = Gap(
        path=Path("demo/services.py"),
        name="start",
        missing_lines=(2, 3),
        missing_branches=(),
        complexity=2,
        changed_uncovered=(),
        has_tests=False,
        existing_tests=(),
        suggested_test=Path("tests/test_services.py"),
        score=6.0,
        risk=Risk.LOW,
    )
    excerpt = source_excerpt(tmp_path, gap)
    assert "2 |     if not name:" in excerpt
    assert "3 |         raise ValueError('empty')" in excerpt


def test_source_excerpt_fills_one_line_holes(tmp_path):
    (tmp_path / "mod.py").write_text(
        "def run():\n    try:\n        missing()\n    except Exception:\n        raise\n",
        encoding="utf-8",
    )
    gap = Gap(
        path=Path("mod.py"),
        name="run",
        missing_lines=(3, 5),
        missing_branches=(),
        complexity=2,
        changed_uncovered=(),
        has_tests=False,
        existing_tests=(),
        suggested_test=Path("tests/test_mod.py"),
        score=3.0,
        risk=Risk.LOW,
    )
    excerpt = source_excerpt(tmp_path, gap)
    assert "2 |     try:" in excerpt
    assert "3 |         missing()" in excerpt
    assert "4 |     except Exception:" in excerpt


def test_render_text_nudge_when_not_changed(capsys):
    gaps = tuple(
        Gap(
            path=Path("demo/services.py"),
            name=f"fn{index}",
            missing_lines=(index,),
            missing_branches=(),
            complexity=1,
            changed_uncovered=(),
            has_tests=False,
            existing_tests=(),
            suggested_test=Path("tests/test_services.py"),
            score=1.0,
            risk=Risk.LOW,
        )
        for index in range(1, 12)
    )
    render_text(_report(gaps))
    out = capsys.readouterr().out
    assert "re-run with testrisk --changed" in out


def test_render_text_no_nudge_when_changed_only(capsys):
    gaps = tuple(
        Gap(
            path=Path("demo/services.py"),
            name=f"fn{index}",
            missing_lines=(index,),
            missing_branches=(),
            complexity=1,
            changed_uncovered=(index,),
            has_tests=False,
            existing_tests=(),
            suggested_test=Path("tests/test_services.py"),
            score=1.0,
            risk=Risk.LOW,
        )
        for index in range(1, 12)
    )
    base = _report(gaps)
    report = GapReport(
        version=base.version,
        root=base.root,
        coverage=base.coverage,
        gaps=gaps,
        changed=base.changed,
        suggested_target=base.suggested_target,
        totals=totals_from_gaps(gaps),
        changed_only=True,
    )
    render_text(report)
    assert "re-run with testrisk --changed" not in capsys.readouterr().out


def test_render_text_stale_coverage(capsys):
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
        risk=Risk.LOW,
    )
    base = _report((gap,))
    report = GapReport(
        version=base.version,
        root=base.root,
        coverage=base.coverage,
        gaps=base.gaps,
        changed=base.changed,
        suggested_target=base.suggested_target,
        stale_coverage=True,
    )
    render_text(report)
    out = capsys.readouterr().out
    assert "Stale" in out
    assert "pytest --cov --cov-report=json" in out


def test_render_json_includes_prompt(capsys):
    render_json(_report(()), prompt=True)
    data = json.loads(capsys.readouterr().out)
    assert "prompt" in data
    assert data["coverage"]["percent"] == 91.7
    assert data["gaps"] == []
