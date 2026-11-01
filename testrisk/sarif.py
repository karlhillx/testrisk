"""SARIF 2.1.0 report for GitHub code scanning and review annotations."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Gap, GapReport, Risk, format_line_ranges
from .version import __version__

_LEVEL = {Risk.HIGH: "error", Risk.MEDIUM: "warning", Risk.LOW: "note"}
_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


def build_sarif(report: GapReport) -> dict[str, object]:
    """Build a SARIF 2.1.0 document from *report*."""
    rules = [
        {
            "id": "untested-behavior",
            "name": "UntestedBehavior",
            "shortDescription": {"text": "Uncovered production behavior with test risk"},
            "helpUri": "https://github.com/karlhillx/testrisk",
        }
    ]
    return {
        "$schema": _SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "testrisk",
                        "version": report.version or __version__,
                        "informationUri": "https://github.com/karlhillx/testrisk",
                        "rules": rules,
                    }
                },
                "results": [_result(gap) for gap in report.gaps],
            }
        ],
    }


def render_sarif(report: GapReport) -> None:
    print(json.dumps(build_sarif(report), indent=2))


def write_sarif(report: GapReport, path: Path | str) -> None:
    Path(path).write_text(json.dumps(build_sarif(report), indent=2) + "\n", encoding="utf-8")


def _result(gap: Gap) -> dict[str, object]:
    start = gap.missing_lines[0] if gap.missing_lines else 1
    message = (
        f"{gap.qualname} is {gap.risk.value} risk "
        f"({format_line_ranges(gap.missing_lines) or 'branches only'} uncovered)"
    )
    return {
        "ruleId": "untested-behavior",
        "level": _LEVEL[gap.risk],
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": gap.path.as_posix()},
                    "region": {"startLine": start},
                }
            }
        ],
        "properties": {
            "score": round(gap.score, 3),
            "test_kind": gap.kind.value,
            "executed_by": list(gap.executed_by),
        },
    }
