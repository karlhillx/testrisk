"""SARIF 2.1.0 renderer."""

from pathlib import Path

from testrisk.models import (
    CoverageSnapshot,
    FileCoverage,
    Gap,
    GapReport,
    Risk,
)
from testrisk.sarif import build_sarif


def test_build_sarif_has_results():
    gap = Gap(
        path=Path("demo/services.py"),
        name="start",
        missing_lines=(15, 16),
        missing_branches=(),
        complexity=2,
        changed_uncovered=(),
        has_tests=False,
        existing_tests=(),
        suggested_test=Path("tests/test_services.py"),
        score=8.0,
        risk=Risk.HIGH,
        executed_by=("tests/test_services.py::test_start",),
    )
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
        line_percent=80.0,
        branch_percent=None,
        covered_lines=8,
        statements=10,
        covered_branches=None,
        branches=None,
    )
    report = GapReport(
        version="1.1.0",
        root=Path("."),
        coverage=snap,
        gaps=(gap,),
        changed=None,
        suggested_target=None,
    )
    doc = build_sarif(report)
    assert doc["version"] == "2.1.0"
    result = doc["runs"][0]["results"][0]
    assert result["level"] == "error"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 15
    assert result["properties"]["executed_by"]
