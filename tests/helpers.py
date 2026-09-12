"""Shared fixtures for building a tiny covered project."""

from __future__ import annotations

import json
from pathlib import Path

SAMPLE_SOURCE = """\
def parse_config(raw):
    if not raw:
        return {}
    if raw.get("debug"):
        return {"debug": True}
    try:
        return {"name": raw["name"]}
    except KeyError:
        raise ValueError("missing name")


class ServiceManager:
    def start(self, name):
        if not name:
            raise ValueError("empty")
        if name == "docker":
            return False
        return True
"""


def write_sample_project(root: Path) -> Path:
    pkg = root / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    source = pkg / "services.py"
    source.write_text(SAMPLE_SOURCE, encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_services.py").write_text(
        "from demo.services import parse_config\n\n"
        "def test_parse_config_empty():\n"
        "    assert parse_config(None) == {}\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    return source


def write_coverage_json(
    root: Path,
    *,
    filename: str = "demo/services.py",
    missing_lines: list[int],
    executed_lines: list[int],
    missing_branches: list[list[int]] | None = None,
    line_percent: float = 70.0,
    branch_percent: float = 50.0,
) -> Path:
    payload = {
        "meta": {"version": "7.16.0", "branch_coverage": True},
        "files": {
            filename: {
                "executed_lines": executed_lines,
                "missing_lines": missing_lines,
                "excluded_lines": [],
                "missing_branches": missing_branches or [],
            }
        },
        "totals": {
            "covered_lines": len(executed_lines),
            "num_statements": len(executed_lines) + len(missing_lines),
            "percent_covered": line_percent,
            "covered_branches": 2,
            "num_branches": 4,
            "percent_covered_branches": branch_percent,
        },
    }
    path = root / "coverage.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
