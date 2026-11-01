"""Changed executable-line numbers from git."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

_DEFAULT_BASES = (
    "origin/main",
    "main",
    "origin/master",
    "master",
)


def ci_base_candidates() -> tuple[str, ...]:
    """GitHub Actions PR target, if the runner exported ``GITHUB_BASE_REF``."""
    ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    if not ref:
        return ()
    ref = ref.removeprefix("refs/heads/")
    if not ref:
        return ()
    return (f"origin/{ref}", ref)


# Isolate from the caller's GIT_DIR / worktree so ``--repo`` is honored.
_GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY")


def _git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _GIT_ENV_DROP}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run_git(
    root: Path,
    args: list[str],
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str] | None:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=root,
            timeout=timeout,
            env=_git_env(),
            creationflags=creationflags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def is_git_repo(root: Path) -> bool:
    result = _run_git(root, ["rev-parse", "--is-inside-work-tree"], timeout=5)
    return result is not None and result.returncode == 0 and result.stdout.strip() == "true"


def resolve_base(root: Path, explicit: str | None) -> str | None:
    """Pick a diff base. ``None`` means git is unavailable."""
    if not is_git_repo(root):
        return None
    if explicit:
        return explicit if _ref_exists(root, explicit) else None
    for candidate in (*ci_base_candidates(), *_DEFAULT_BASES):
        if _ref_exists(root, candidate):
            return candidate
    return "HEAD"


def changed_lines(root: Path, base: str | None) -> dict[Path, frozenset[int]]:
    """Map repo-relative paths to new-file line numbers changed since *base*."""
    if base is None:
        return {}
    spec = _diff_spec(root, base)
    if spec is None:
        return {}
    result = _run_git(
        root,
        ["diff", "-U0", "--no-color", "--no-ext-diff", spec, "--", "*.py"],
        timeout=15,
    )
    if result is None or result.returncode != 0:
        return {}
    return parse_diff(result.stdout)


def file_commit_counts(root: Path, *, since: str = "90.days") -> dict[Path, int]:
    """How often each ``.py`` file changed in *since* (git log name-only)."""
    if not is_git_repo(root):
        return {}
    result = _run_git(
        root,
        ["log", "--pretty=format:", "--name-only", f"--since={since}", "--", "*.py"],
        timeout=20,
    )
    if result is None or result.returncode != 0:
        return {}
    counts: dict[Path, int] = {}
    for line in result.stdout.splitlines():
        text = line.strip().replace("\\", "/")
        if not text.endswith(".py"):
            continue
        path = Path(text)
        counts[path] = counts.get(path, 0) + 1
    return counts


def dirty_python_files(root: Path) -> tuple[Path, ...]:
    """Modified, staged, or untracked ``.py`` files in the working tree."""
    if not is_git_repo(root):
        return ()
    names: set[Path] = set()
    queries = (
        ["ls-files", "-m", "-o", "--exclude-standard", "--", "*.py"],
        ["diff", "--name-only", "--cached", "--", "*.py"],
    )
    for args in queries:
        result = _run_git(root, args, timeout=5)
        if result is None or result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            text = line.strip().replace("\\", "/")
            if text.endswith(".py"):
                names.add(Path(text))
    return tuple(sorted(names, key=lambda path: path.as_posix()))


def _diff_spec(root: Path, base: str) -> str | None:
    if base == "HEAD":
        return "HEAD"
    merge = _merge_base(root, base)
    return merge or base


def _merge_base(root: Path, base: str) -> str | None:
    result = _run_git(root, ["merge-base", base, "HEAD"], timeout=5)
    if result is None:
        return None
    sha = result.stdout.strip()
    if result.returncode != 0 or not sha:
        return None
    return sha


def _ref_exists(root: Path, ref: str) -> bool:
    result = _run_git(root, ["rev-parse", "--verify", "--quiet", ref], timeout=5)
    return result is not None and result.returncode == 0


def parse_diff(diff_text: str) -> dict[Path, frozenset[int]]:
    """Parse unified ``git diff -U0`` output into new-file line numbers."""
    current: Path | None = None
    collected: dict[Path, set[int]] = {}
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            raw = line[4:]
            if raw == "/dev/null":
                current = None
                continue
            if raw.startswith("b/"):
                raw = raw[2:]
            current = Path(raw.replace("\\", "/"))
            collected.setdefault(current, set())
            continue
        match = _HUNK.match(line)
        if match is None or current is None:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        if count <= 0:
            continue
        collected[current].update(range(start, start + count))
    return {path: frozenset(lines) for path, lines in collected.items() if lines}
