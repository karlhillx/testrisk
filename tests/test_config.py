"""[tool.testrisk] loading."""

import pytest

from testrisk.config import load_settings, parse_settings
from testrisk.errors import GapError
from testrisk.models import Risk


def test_load_settings_missing_file(tmp_path):
    settings = load_settings(tmp_path)
    assert settings.top == 10
    assert settings.omit == ()
    assert settings.fail_on_risk is None
    assert settings.default_omit is True


def test_load_settings_without_table(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert load_settings(tmp_path).changed is False


def test_parse_settings_kebab_and_aliases():
    settings = parse_settings(
        {
            "base": "origin/develop",
            "top": 3,
            "changed": True,
            "fail-under-changed": 90,
            "fail-on-risk": "high",
            "min-risk": "MEDIUM",
            "exclude": ["**/migrations/**"],
            "files": ["src/**"],
            "explain": True,
            "weak-only": True,
            "fail-on-weak": True,
            "default-omit": False,
            "baseline": ".testrisk-baseline",
            "weights": {"changed-uncovered": 5.0, "churn": 0.5, "fan-in": 0.2},
        }
    )
    assert settings.base == "origin/develop"
    assert settings.top == 3
    assert settings.changed is True
    assert settings.fail_under_changed == 90
    assert settings.fail_on_risk is Risk.HIGH
    assert settings.min_risk is Risk.MEDIUM
    assert settings.omit == ("**/migrations/**",)
    assert settings.include == ("src/**",)
    assert settings.explain is True
    assert settings.weak_only is True
    assert settings.fail_on_weak is True
    assert settings.default_omit is False
    assert settings.baseline == ".testrisk-baseline"
    assert settings.weights.changed_uncovered == 5.0
    assert settings.weights.churn == 0.5
    assert settings.weights.fan_in == 0.2
    assert settings.weights.missing_lines == 1.0


def test_parse_settings_rejects_bad_risk():
    with pytest.raises(GapError, match="risk"):
        parse_settings({"fail-on-risk": "critical"})


def test_parse_settings_rejects_bad_top():
    with pytest.raises(GapError, match="top"):
        parse_settings({"top": -1})


def test_load_settings_reads_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.testrisk]\nomit = ['**/generated/**']\ntop = 4\n",
        encoding="utf-8",
    )
    settings = load_settings(tmp_path)
    assert settings.omit == ("**/generated/**",)
    assert settings.top == 4


def test_analyze_honors_config_default_omit(tmp_path):
    from helpers import write_coverage_json, write_sample_project

    from testrisk import analyze

    write_sample_project(tmp_path)
    (tmp_path / "demo" / "__init__.py").write_text(
        "def leftover():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n\n[tool.testrisk]\ndefault-omit = false\n",
        encoding="utf-8",
    )
    write_coverage_json(
        tmp_path,
        filename="demo/__init__.py",
        missing_lines=[2],
        executed_lines=[],
    )
    report = analyze(tmp_path, top=0)
    assert any(gap.path.as_posix() == "demo/__init__.py" for gap in report.gaps)
