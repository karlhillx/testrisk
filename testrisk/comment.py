"""PR comment and GitHub step-summary markdown."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .models import GapReport, format_line_ranges
from .version import __version__

MARKER = "<!-- testrisk-report -->"
_API = "https://api.github.com"


def render_markdown(report: GapReport) -> str:
    """Compact markdown for a PR comment or job summary."""
    lines = [
        MARKER,
        f"## testrisk {report.version or __version__}",
        "",
    ]
    if report.changed is not None and report.changed.statements:
        missing = report.changed.statements - report.changed.covered
        pct = report.changed.percent or 0.0
        lines.append(f"Changed-line coverage **{pct:.1f}%** · {missing} uncovered.")
    else:
        lines.append(f"Line coverage **{report.coverage.line_percent:.1f}%**.")
    if report.waived:
        lines.append(f"{len(report.waived)} waived baseline gap(s) omitted from gates.")
    lines.append("")
    if not report.gaps:
        lines.append("No test gaps in this scope.")
        return "\n".join(lines) + "\n"
    lines.append("| Risk | Gap | Missing | Tests |")
    lines.append("| --- | --- | --- | --- |")
    for gap in report.gaps:
        tests = ", ".join(gap.executed_by[:2]) if gap.executed_by else gap.kind.value
        missing = format_line_ranges(gap.missing_lines) or "branches"
        lines.append(f"| {gap.risk.value} | `{gap.qualname}` | {missing} | {tests} |")
    if report.totals.matched > report.totals.shown:
        lines.append("")
        lines.append(f"Showing {report.totals.shown} of {report.totals.matched} gaps.")
    return "\n".join(lines) + "\n"


def write_step_summary(markdown: str, path: Path | str | None = None) -> None:
    """Append markdown to ``GITHUB_STEP_SUMMARY`` when that env var is set."""
    target = path if path is not None else os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    with Path(target).open("a", encoding="utf-8") as handle:
        handle.write(markdown)
        if not markdown.endswith("\n"):
            handle.write("\n")


def upsert_pr_comment(
    markdown: str,
    *,
    token: str | None = None,
    repository: str | None = None,
    event_path: Path | str | None = None,
) -> bool:
    """Create or update the testrisk comment on the current pull request."""
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repository = repository or os.environ.get("GITHUB_REPOSITORY")
    raw_event = event_path or os.environ.get("GITHUB_EVENT_PATH")
    if not token or not repository or not raw_event:
        return False
    number = _pr_number(Path(raw_event))
    if number is None:
        return False
    existing = _find_comment(token, repository, number)
    if existing is None:
        _request(
            "POST",
            f"/repos/{repository}/issues/{number}/comments",
            token,
            {"body": markdown},
        )
    else:
        _request(
            "PATCH",
            f"/repos/{repository}/issues/comments/{existing}",
            token,
            {"body": markdown},
        )
    return True


def _pr_number(event_path: Path) -> int | None:
    try:
        payload = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pull = payload.get("pull_request")
    if isinstance(pull, dict) and isinstance(pull.get("number"), int):
        return pull["number"]
    issue = payload.get("issue")
    if (
        isinstance(issue, dict)
        and issue.get("pull_request")
        and isinstance(issue.get("number"), int)
    ):
        return issue["number"]
    return None


def _find_comment(token: str, repository: str, number: int) -> int | None:
    comments = _request(
        "GET",
        f"/repos/{repository}/issues/{number}/comments?per_page=100",
        token,
    )
    if not isinstance(comments, list):
        return None
    for item in comments:
        if not isinstance(item, dict):
            continue
        body = item.get("body")
        if isinstance(body, str) and MARKER in body and isinstance(item.get("id"), int):
            return item["id"]
    return None


def _request(
    method: str,
    path: str,
    token: str,
    payload: dict[str, object] | None = None,
) -> object:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{_API}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "testrisk",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
