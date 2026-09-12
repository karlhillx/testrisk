"""Doctor inspection."""

import os
from pathlib import Path

from helpers import write_coverage_json, write_sample_project

import testrisk.doctor as doctor
from testrisk.doctor import inspect_environment, print_doctor


def test_doctor_ok_when_coverage_exists(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(tmp_path, missing_lines=[2], executed_lines=[1])
    report = inspect_environment(str(tmp_path))
    assert report.ok
    assert report.coverage_file is not None
    assert report.coverage_file.as_posix() == "coverage.json"
    assert report.next_command == "testrisk --changed"


def test_doctor_reports_missing_coverage(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    report = inspect_environment(str(tmp_path))
    assert not report.ok
    assert report.coverage_error
    assert "pytest --cov" in report.generate


def test_doctor_missing_prints_generate(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    code = print_doctor(inspect_environment(str(tmp_path)))
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert code == 1
    assert "pytest --cov --cov-report=json" in combined
    assert "testrisk --changed" in combined


def test_doctor_ok_prints_next_command(tmp_path, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(tmp_path, missing_lines=[2], executed_lines=[1])
    code = print_doctor(inspect_environment(str(tmp_path)))
    out = capsys.readouterr().out
    assert code == 0
    assert "Ready to rank test gaps." in out
    assert "testrisk --changed" in out


def test_doctor_stale_print_stays_on_stdout(tmp_path, capsys):
    write_sample_project(tmp_path)
    write_coverage_json(tmp_path, missing_lines=[2], executed_lines=[1])
    report = inspect_environment(str(tmp_path))
    report = doctor.DoctorReport(
        python=report.python,
        version=report.version,
        repo=report.repo,
        coverage_file=report.coverage_file,
        coverage_error=report.coverage_error,
        git=report.git,
        base=report.base,
        config_file=report.config_file,
        stale_coverage=True,
        stale_files=("demo/services.py",),
    )
    code = print_doctor(report)
    captured = capsys.readouterr()
    assert code == 0
    assert "Stale" in captured.out
    assert "pytest --cov --cov-report=json" in captured.out
    assert captured.err == ""


def test_doctor_stale_when_source_newer(tmp_path, monkeypatch):
    write_sample_project(tmp_path)
    coverage = write_coverage_json(tmp_path, missing_lines=[2], executed_lines=[1])
    source = tmp_path / "demo" / "services.py"
    os.utime(coverage, (1_000_000, 1_000_000))
    os.utime(source, (2_000_000, 2_000_000))
    monkeypatch.setattr(doctor, "is_git_repo", lambda _root: True)
    monkeypatch.setattr(doctor, "resolve_base", lambda _root, _base: "HEAD")
    monkeypatch.setattr(
        doctor,
        "changed_lines",
        lambda _root, _base: {Path("demo/services.py"): frozenset({1})},
    )
    report = inspect_environment(str(tmp_path))
    assert report.stale_coverage is True
    assert "demo/services.py" in report.stale_files
