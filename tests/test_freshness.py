"""Coverage freshness against changed sources."""

import os
from pathlib import Path

from testrisk.freshness import coverage_is_stale, stale_sources


def test_stale_when_source_newer_than_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr("testrisk.freshness.dirty_python_files", lambda _root: ())
    coverage = tmp_path / "coverage.json"
    source = tmp_path / "mod.py"
    coverage.write_text("{}", encoding="utf-8")
    source.write_text("x = 1\n", encoding="utf-8")
    os.utime(coverage, (1_000_000, 1_000_000))
    os.utime(source, (2_000_000, 2_000_000))
    changed = {Path("mod.py"): frozenset({1})}
    assert stale_sources(tmp_path, coverage, changed) == (Path("mod.py"),)
    assert coverage_is_stale(tmp_path, coverage, changed)


def test_fresh_when_coverage_newer(tmp_path, monkeypatch):
    monkeypatch.setattr("testrisk.freshness.dirty_python_files", lambda _root: ())
    coverage = tmp_path / "coverage.json"
    source = tmp_path / "mod.py"
    coverage.write_text("{}", encoding="utf-8")
    source.write_text("x = 1\n", encoding="utf-8")
    os.utime(source, (1_000_000, 1_000_000))
    os.utime(coverage, (2_000_000, 2_000_000))
    changed = {Path("mod.py"): frozenset({1})}
    assert stale_sources(tmp_path, coverage, changed) == ()
    assert coverage_is_stale(tmp_path, coverage, changed) is False


def test_within_slack_is_not_stale(tmp_path, monkeypatch):
    monkeypatch.setattr("testrisk.freshness.dirty_python_files", lambda _root: ())
    coverage = tmp_path / "coverage.json"
    source = tmp_path / "mod.py"
    coverage.write_text("{}", encoding="utf-8")
    source.write_text("x = 1\n", encoding="utf-8")
    os.utime(coverage, (2_000_000, 2_000_000))
    os.utime(source, (2_000_000.4, 2_000_000.4))
    assert stale_sources(tmp_path, coverage, {Path("mod.py"): frozenset({1})}) == ()


def test_missing_coverage_is_not_stale(tmp_path, monkeypatch):
    monkeypatch.setattr("testrisk.freshness.dirty_python_files", lambda _root: ())
    assert stale_sources(tmp_path, tmp_path / "missing.json", {Path("mod.py"): frozenset()}) == ()


def test_ignores_non_python_and_missing_sources(tmp_path, monkeypatch):
    monkeypatch.setattr("testrisk.freshness.dirty_python_files", lambda _root: ())
    coverage = tmp_path / "coverage.json"
    coverage.write_text("{}", encoding="utf-8")
    os.utime(coverage, (1_000_000, 1_000_000))
    changed = {
        Path("notes.md"): frozenset({1}),
        Path("gone.py"): frozenset({1}),
    }
    assert stale_sources(tmp_path, coverage, changed) == ()


def test_dirty_untracked_file_can_make_coverage_stale(tmp_path, monkeypatch):
    coverage = tmp_path / "coverage.json"
    extra = tmp_path / "new.py"
    coverage.write_text("{}", encoding="utf-8")
    extra.write_text("x = 1\n", encoding="utf-8")
    os.utime(coverage, (1_000_000, 1_000_000))
    os.utime(extra, (2_000_000, 2_000_000))
    monkeypatch.setattr("testrisk.freshness.dirty_python_files", lambda _root: (Path("new.py"),))
    assert stale_sources(tmp_path, coverage, {}) == (Path("new.py"),)
