"""Unified diff parsing and git integration."""

import subprocess
from pathlib import Path

from testrisk.gitdiff import (
    changed_lines,
    ci_base_candidates,
    dirty_python_files,
    parse_diff,
    resolve_base,
)


def test_parse_diff_collects_added_ranges():
    diff = """\
diff --git a/src/foo.py b/src/foo.py
--- a/src/foo.py
+++ b/src/foo.py
@@ -44,0 +45,4 @@
+one
+two
+three
+four
@@ -100 +103,0 @@
-deleted
"""
    result = parse_diff(diff)
    assert result[Path("src/foo.py")] == frozenset({45, 46, 47, 48})


def test_parse_diff_skips_deleted_files():
    diff = """\
diff --git a/gone.py b/gone.py
--- a/gone.py
+++ /dev/null
@@ -1,3 +0,0 @@
-a
-b
-c
"""
    assert parse_diff(diff) == {}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_changed_lines_from_real_repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "dev@example.com")
    _git(tmp_path, "config", "user.name", "Dev")
    source = tmp_path / "mod.py"
    source.write_text("def a():\n    return 1\n", encoding="utf-8")
    _git(tmp_path, "add", "mod.py")
    _git(tmp_path, "commit", "-m", "base")
    source.write_text("def a():\n    return 1\n\ndef b():\n    return 2\n", encoding="utf-8")
    result = changed_lines(tmp_path, "HEAD")
    assert Path("mod.py") in result
    assert result[Path("mod.py")]
    assert Path("mod.py") in dirty_python_files(tmp_path)
    extra = tmp_path / "new.py"
    extra.write_text("x = 1\n", encoding="utf-8")
    assert Path("new.py") in dirty_python_files(tmp_path)


def test_resolve_base_none_outside_git(tmp_path):
    assert resolve_base(tmp_path, None) is None


def test_ci_base_candidates(monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    assert ci_base_candidates() == ()
    monkeypatch.setenv("GITHUB_BASE_REF", "refs/heads/develop")
    assert ci_base_candidates() == ("origin/develop", "develop")
