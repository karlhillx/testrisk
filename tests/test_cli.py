"""CLI flags and exit codes."""

import json
import sys
from pathlib import Path

import pytest
from helpers import write_coverage_json, write_sample_project

import testrisk.engine as engine
from testrisk import cli


def _run(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["testrisk", *argv])
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
    assert "pytest --cov --cov-report=json" in captured.err
    assert "testrisk --changed" in captured.err


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


def test_cli_fail_on_risk(tmp_path, monkeypatch, capsys):
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
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--fail-on-risk", "HIGH"])
    assert code == 1
    assert "fail-on-risk HIGH" in capsys.readouterr().err


def test_cli_no_default_omit(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    (tmp_path / "demo" / "__init__.py").write_text(
        "def leftover():\n    return 1\n",
        encoding="utf-8",
    )
    write_coverage_json(
        tmp_path,
        filename="demo/__init__.py",
        missing_lines=[2],
        executed_lines=[],
    )
    hidden = _run(monkeypatch, ["--repo", str(tmp_path), "--top", "0"])
    hidden_out = capsys.readouterr().out
    assert hidden == 0
    assert "leftover" not in hidden_out
    shown = _run(monkeypatch, ["--repo", str(tmp_path), "--top", "0", "--no-default-omit"])
    shown_out = capsys.readouterr().out
    assert shown == 0
    assert "leftover" in shown_out


def test_cli_exclude(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--exclude", "demo/**"])
    out = capsys.readouterr().out
    assert code == 0
    assert "No test gaps found" in out


def test_cli_explain(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--explain"])
    out = capsys.readouterr().out
    assert code == 0
    assert "why" in out
    assert "lines " in out


def test_cli_min_risk(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[2],
        executed_lines=[1],
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--min-risk", "HIGH", "--top", "0"])
    out = capsys.readouterr().out
    assert code == 0
    assert "No test gaps found" in out


def test_cli_json_includes_score_parts(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert data["gaps"]
    assert "score_parts" in data["gaps"][0]
    assert data["gaps"][0]["test_kind"] in {"none", "indirect", "weak", "meaningful"}
    assert "matched" in data
    assert "totals" in data
    assert "indirect" in data["totals"]["checks"]
    assert data["totals"]["shown"] == len(data["gaps"])
    assert "stale_coverage" in data
    assert data["changed_only"] is False


def test_cli_prompt_includes_source(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--prompt"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Source:" in out
    assert " | " in out


def test_cli_config_fail_on_risk(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n\n[tool.testrisk]\nfail-on-risk = 'HIGH'\n",
        encoding="utf-8",
    )
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
    code = _run(monkeypatch, ["--repo", str(tmp_path)])
    assert code == 1
    assert "fail-on-risk HIGH" in capsys.readouterr().err


def test_cli_fail_on_weak(tmp_path, monkeypatch, capsys):
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
        missing_lines=[15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--fail-on-weak"])
    assert code == 1
    assert "ceremonial related tests" in capsys.readouterr().err


def test_cli_weak_only(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9, 15, 16],
        executed_lines=list(range(1, 8)),
    )
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--weak-only", "--top", "0"])
    out = capsys.readouterr().out
    assert code == 0
    assert "ServiceManager.start" in out
    assert "parse_config" not in out


def test_cli_doctor_json(tmp_path, monkeypatch, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(tmp_path, missing_lines=[2], executed_lines=[1])
    code = _run(monkeypatch, ["--repo", str(tmp_path), "--doctor", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert data["coverage_file"] == "coverage.json"
    assert data["config_file"] is None
    assert data["next"] == "testrisk --changed"
    assert "stale_coverage" in data


def test_package_main_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["testrisk", "--help"])
    from testrisk.__main__ import _main

    with pytest.raises(SystemExit) as exc:
        _main()
    assert exc.value.code == 0
    assert "highest-value" in capsys.readouterr().out
