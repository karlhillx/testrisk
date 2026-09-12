"""CLI flags and exit codes."""

import json
import sys
from pathlib import Path

import pytest
from helpers import write_coverage_json, write_sample_project

import testgap.engine as engine
from testgap import cli


def _run(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["test-gap", *argv])
    return cli.main()


def test_cli_text_report(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9, 15, 16],
        executed_lines=list(range(1, 8)),
        missing_branches=[[16, 0]],
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Highest-value test gaps" in out
    assert "ServiceManager.start" in out or "parse_config" in out


def test_cli_json(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "gaps" in data
    assert data["coverage"]["source"] == "coverage.json"


def test_cli_prompt(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--prompt"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Write focused unit tests" in out
    assert "Uncovered:" in out


def test_cli_quiet_prints_target(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--quiet"])
    out = capsys.readouterr().out.strip()
    assert code == 0
    assert out == "tests/test_services.py"


def test_cli_missing_coverage(tmp_path, monkeypatch, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    code = _run(monkeypatch, ["--repo", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "No coverage data found" in captured.err


def test_cli_missing_coverage_json(tmp_path, monkeypatch, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 1
    assert "error" in data


def test_cli_rejects_negative_top(tmp_path, monkeypatch, capsys):
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--top", "-1"])
    assert code == 2
    assert "--top" in capsys.readouterr().err


def test_cli_fail_under_changed(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    monkeypatch.setattr(
        engine,
        "changed_lines",
        lambda _root, _base: {Path("demo/services.py"): frozenset({15, 16})},
    )
    monkeypatch.setattr(engine, "resolve_base", lambda _root, _base: "HEAD")
    code = _run(
        monkeypatch,
        ["--repo", str(tmp_path), "--fail-under-changed", "95"],
    )
    assert code == 1
    assert "below 95.0%" in capsys.readouterr().err


def test_cli_doctor_json(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(tmp_path, missing_lines=[2], executed_lines=[1])
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--doctor", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert data["coverage_file"] == "coverage.json"


def test_package_main_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["testgap", "--help"])
    from testgap.__main__ import _main

    with pytest.raises(SystemExit) as exc:
        _main()
    assert exc.value.code == 0
    assert "highest-value" in capsys.readouterr().out
