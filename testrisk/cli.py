#!/usr/bin/env python3
"""
testrisk CLI — rank the highest-value Python test gaps.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import traceback

from .comment import render_markdown, upsert_pr_comment, write_step_summary
from .config import load_settings
from .discover import resolve_repo_path
from .doctor import inspect_environment, print_doctor
from .engine import Options, analyze
from .errors import GapError
from .models import ChangedCoverage, Risk, parse_risk, risk_at_least
from .report import render_json, render_prompt, render_text
from .sarif import render_sarif, write_sarif
from .ui import configure_ui, get_ui
from .version import __version__


def _risk_arg(value: str) -> Risk:
    try:
        return parse_risk(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _cli_dispatch() -> int:
    parser = argparse.ArgumentParser(
        prog="testrisk",
        description="Rank the highest-value untested Python behavior",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pytest --cov --cov-report=json            # generate coverage first
  uvx testrisk --changed                    # everyday command: this branch
  testrisk --changed                        # Only gaps on git-changed lines
  testrisk --top 10                         # Limit the list
  testrisk --file src/foo.py                # Restrict to one file
  testrisk --file 'src/foo/**'              # Glob include
  testrisk --exclude '**/migrations/**'     # Skip generated / noisy paths
  testrisk --json                           # Machine-readable report (schema testrisk.gap/v2)
  testrisk --format sarif                   # GitHub code scanning
  testrisk --prompt                         # Agent task from the evidence
  testrisk --explain                        # Show score breakdown
  testrisk --write-baseline                 # Snapshot current gaps as waived
  pytest --cov --testrisk                   # Rank after the suite
  testrisk --weak-only                      # Gaps with missing or ceremonial tests
  testrisk --fail-under-changed 95          # CI gate on changed-line coverage
  testrisk --fail-on-risk HIGH              # CI gate on risk
  testrisk --fail-on-weak                   # CI gate on ceremonial related tests
  testrisk --doctor                         # Check coverage data and git
  python -m testrisk --version              # If testrisk is not on PATH

Defaults can be set in pyproject.toml under [tool.testrisk].
        """,
    )
    parser.add_argument(
        "--repo",
        "-r",
        default=".",
        help="Path to repository (default: . — walk up for pyproject.toml / .git)",
    )
    parser.add_argument(
        "--coverage",
        "-c",
        default=None,
        metavar="PATH",
        help="coverage.json, coverage.xml, or .coverage (default: search the repo)",
    )
    parser.add_argument(
        "--changed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Only show gaps that intersect git-changed lines (default: config or off)",
    )
    parser.add_argument(
        "--base",
        default=None,
        metavar="REF",
        help="Git ref to diff against (default: GITHUB_BASE_REF, origin/main, main, HEAD)",
    )
    parser.add_argument(
        "--top",
        "-n",
        type=int,
        default=None,
        metavar="N",
        help="How many gaps to show (default: 10; 0 means all)",
    )
    parser.add_argument(
        "--file",
        "-f",
        dest="files",
        action="append",
        metavar="PATH",
        help="Restrict ranking to this source file or glob (repeatable)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        dest="exclude",
        action="append",
        metavar="GLOB",
        help="Skip source paths matching this glob (repeatable; merges with config omit)",
    )
    parser.add_argument(
        "--default-omit",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Skip __init__.py and migrations/ (default: on; disable with --no-default-omit)",
    )
    parser.add_argument(
        "--min-risk",
        type=_risk_arg,
        default=None,
        metavar="LEVEL",
        help="Hide gaps below this risk (LOW, MEDIUM, HIGH)",
    )
    parser.add_argument(
        "--weak-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Only show gaps with no meaningful related tests (missing or ceremonial)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the report as JSON (same as --format json)",
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Print an evidence-based task for an AI coding agent",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "prompt", "sarif"],
        default=None,
        help="Output format (default: text; --json / --prompt still work)",
    )
    parser.add_argument(
        "--sarif",
        default=None,
        metavar="PATH",
        help="Also write a SARIF 2.1.0 report to PATH",
    )
    parser.add_argument(
        "--comment",
        action="store_true",
        help="Write a PR comment / GitHub step summary when GITHUB_* is set",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        metavar="PATH",
        help="Waive qualnames in this file (default: .testrisk-baseline if present)",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Ignore .testrisk-baseline and config baseline",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write the current matched gaps to the baseline file",
    )
    parser.add_argument(
        "--explain",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show how each score was assembled",
    )
    parser.add_argument(
        "--fail-under-changed",
        type=float,
        default=None,
        metavar="PCT",
        help="Exit 1 if changed-line coverage is below this percent",
    )
    parser.add_argument(
        "--fail-on-risk",
        type=_risk_arg,
        default=None,
        metavar="LEVEL",
        help="Exit 1 if any matched gap is at least this risk (LOW, MEDIUM, HIGH)",
    )
    parser.add_argument(
        "--fail-on-weak",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Exit 1 if any matched gap has ceremonial related tests",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check Python, coverage data, and git, then exit",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Print only the suggested next test file",
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Color output (default: auto; also NO_COLOR / FORCE_COLOR)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a traceback on unexpected errors",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()
    output = _output_format(args)
    color = "never" if output in {"json", "prompt", "sarif"} else args.color
    configure_ui(
        color=color,
        quiet=bool(args.quiet and output == "text"),
    )
    ui = get_ui()

    if args.top is not None and args.top < 0:
        ui.error("--top must be >= 0")
        return 2
    if args.fail_under_changed is not None and not 0 <= args.fail_under_changed <= 100:
        ui.error("--fail-under-changed must be between 0 and 100")
        return 2

    try:
        repo_path = resolve_repo_path(args.repo)
    except OSError as exc:
        ui.error(f"Could not resolve path {args.repo!r}: {exc}")
        return 1
    if not repo_path.is_dir():
        ui.error(f"Not a directory: {repo_path}")
        return 1

    if args.doctor:
        return print_doctor(
            inspect_environment(str(repo_path), args.coverage),
            json_output=args.json,
        )

    try:
        settings = load_settings(repo_path)
    except GapError as exc:
        ui.error(str(exc))
        return 1

    changed_only = settings.changed if args.changed is None else args.changed
    top = settings.top if args.top is None else args.top
    explain = settings.explain if args.explain is None else args.explain
    fail_under = (
        settings.fail_under_changed if args.fail_under_changed is None else args.fail_under_changed
    )
    fail_on_risk = settings.fail_on_risk if args.fail_on_risk is None else args.fail_on_risk
    min_risk = settings.min_risk if args.min_risk is None else args.min_risk
    weak_only = settings.weak_only if args.weak_only is None else args.weak_only
    fail_on_weak = settings.fail_on_weak if args.fail_on_weak is None else args.fail_on_weak
    default_omit = settings.default_omit if args.default_omit is None else args.default_omit
    if args.no_baseline:
        baseline: str | None = ""
    elif args.baseline is not None:
        baseline = args.baseline
    else:
        baseline = settings.baseline
    base = args.base if args.base is not None else settings.base
    files = tuple(args.files) if args.files else settings.include
    omit = tuple(dict.fromkeys([*settings.omit, *(args.exclude or ())]))

    try:
        report = analyze(
            options=Options(
                root=repo_path,
                coverage=args.coverage,
                changed_only=changed_only,
                base=base,
                files=files,
                omit=omit,
                top=top,
                min_risk=min_risk,
                weights=settings.weights,
                weak_only=weak_only,
                default_omit=default_omit,
                baseline=baseline,
                write_baseline=args.write_baseline,
                apply_config=False,
            )
        )
    except GapError as exc:
        if output == "json":
            print(json.dumps({"error": str(exc).split("\n", 1)[0]}))
            return 1
        ui.error(str(exc))
        return 1

    if args.quiet and output == "text":
        if report.suggested_target is not None:
            print(report.suggested_target.as_posix())
        elif report.gaps:
            print(report.gaps[0].suggested_test.as_posix())
    elif output == "json":
        render_json(report, prompt=args.prompt)
    elif output == "prompt":
        render_prompt(report)
    elif output == "sarif":
        render_sarif(report)
    else:
        render_text(report, explain=explain)

    if args.sarif:
        write_sarif(report, args.sarif)
    if args.comment:
        markdown = render_markdown(report)
        write_step_summary(markdown)
        upsert_pr_comment(markdown)

    silent = output in {"json", "sarif"}
    if fail_on_risk is not None:
        code = _check_risk_floor(report.worst_risk, fail_on_risk, report.matched, silent)
        if code != 0:
            return code
    if fail_on_weak:
        code = _check_weak_floor(report.weak_matched, silent)
        if code != 0:
            return code
    if fail_under is not None:
        return _check_changed_floor(report.changed, fail_under, silent)
    return 0


def _output_format(args: argparse.Namespace) -> str:
    if args.format:
        return args.format
    if args.json:
        return "json"
    if args.prompt:
        return "prompt"
    return "text"


def _check_risk_floor(
    peak: Risk | None,
    floor: Risk,
    matched: int,
    json_output: bool,
) -> int:
    if peak is None or not risk_at_least(peak, floor):
        return 0
    if not json_output:
        noun = "gap" if matched == 1 else "gaps"
        get_ui().error(f"{matched} {noun} meet --fail-on-risk {floor.value} (worst {peak.value})")
    return 1


def _check_weak_floor(weak_matched: int, json_output: bool) -> int:
    if weak_matched <= 0:
        return 0
    if not json_output:
        noun = "gap" if weak_matched == 1 else "gaps"
        get_ui().error(f"{weak_matched} {noun} have ceremonial related tests (--fail-on-weak)")
    return 1


def _check_changed_floor(changed: ChangedCoverage | None, floor: float, json_output: bool) -> int:
    if changed is None:
        ui = get_ui()
        msg = "Cannot enforce --fail-under-changed without git"
        if json_output:
            return 1
        ui.error(msg)
        return 1
    if changed.statements == 0:
        return 0
    percent = changed.percent or 0.0
    if percent + 1e-9 >= floor:
        return 0
    if not json_output:
        get_ui().error(f"Changed-line coverage {_fmt(percent)} is below {_fmt(floor)}")
    return 1


def _fmt(value: float) -> str:
    return f"{value:.1f}%"


def _line_buffer_stdio() -> None:
    """Keep banners ahead of following output when stdout is a pipe."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(OSError, ValueError):
            reconfigure(line_buffering=True)


def main() -> int:
    _line_buffer_stdio()
    try:
        return _cli_dispatch()
    except KeyboardInterrupt:
        get_ui().error("Interrupted.")
        return 130
    except BrokenPipeError:
        with contextlib.suppress(OSError):
            sys.stdout.close()
        return 0
    except Exception as exc:
        ui = get_ui()
        ui.error("testrisk hit an unexpected error.")
        ui.error(f"{type(exc).__name__}: {exc}")
        if "--verbose" in sys.argv or os.environ.get("TESTRISK_DEBUG"):
            traceback.print_exc()
        else:
            ui.note(
                "Re-run with --verbose or TESTRISK_DEBUG=1 for a traceback.",
                persist=True,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
