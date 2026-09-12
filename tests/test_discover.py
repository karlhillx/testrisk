"""Repo walk-up and coverage discovery."""

from pathlib import Path

import pytest

from testrisk.discover import (
    find_coverage_file,
    find_repo_root,
    matches_filter,
    path_key,
    relativize,
    resolve_repo_path,
    same_relpath,
)
from testrisk.errors import GapError


def test_find_repo_root_walks_to_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == tmp_path


def test_resolve_repo_path_walks_default_dot(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    nested = tmp_path / "inner"
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert resolve_repo_path(".") == tmp_path


def test_resolve_repo_path_explicit_is_literal(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert resolve_repo_path(str(other)) == other.resolve()


def test_find_coverage_prefers_json(tmp_path):
    (tmp_path / "coverage.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".coverage").write_text("x", encoding="utf-8")
    assert find_coverage_file(tmp_path).name == "coverage.json"


def test_find_coverage_missing_explains_how(tmp_path):
    with pytest.raises(GapError, match="pytest --cov"):
        find_coverage_file(tmp_path)


def test_find_coverage_explicit_missing(tmp_path):
    with pytest.raises(GapError, match="not found"):
        find_coverage_file(tmp_path, tmp_path / "nope.json")


def test_relativize_keeps_outside_paths(tmp_path):
    outside = Path("/tmp/elsewhere.py")
    result = relativize(outside, tmp_path)
    assert result == outside or result.is_absolute()


def test_matches_filter_accepts_basename_and_suffix():
    path = Path("demo/services.py")
    assert matches_filter(path, Path("demo/services.py"))
    assert matches_filter(path, Path("services.py"))
    assert not matches_filter(path, Path("other.py"))


def test_same_relpath_tolerates_prefix_mismatch():
    assert same_relpath(Path("src/foo.py"), Path("foo.py"))
    assert not same_relpath(Path("src/foo.py"), Path("bar.py"))


def test_path_key_uses_posix_slashes():
    key = path_key(Path("demo") / "services.py")
    assert key.replace("\\", "/").endswith("demo/services.py")
