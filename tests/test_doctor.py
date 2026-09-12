"""Doctor inspection."""

from helpers import write_coverage_json, write_sample_project

from testrisk.doctor import inspect_environment


def test_doctor_ok_when_coverage_exists(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(tmp_path, missing_lines=[2], executed_lines=[1])
    report = inspect_environment(str(tmp_path))
    assert report.ok
    assert report.coverage_file is not None
    assert report.coverage_file.as_posix() == "coverage.json"


def test_doctor_reports_missing_coverage(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    report = inspect_environment(str(tmp_path))
    assert not report.ok
    assert report.coverage_error
