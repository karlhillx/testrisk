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

from .discover import resolve_repo_path
from .doctor import inspect_environment, print_doctor
from .engine import analyze
from .errors import GapError
from .models import ChangedCoverage
from .report import render_json, render_prompt, render_text
from .ui import configure_ui, get_ui
from .version import __version__


def _cli_dispatch() -> int:
    parser = argparse.ArgumentParser(
        prog="testrisk",
        description="Rank the highest-value untested Python behavior",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uvx testrisk                              # zero-install; rank gaps
  testrisk                                  # Use coverage.json / .coverage
  testrisk --changed                        # Only gaps on git-changed lines
  testrisk --top 10                         # Limit the list
  testrisk --file src/foo.py                # Restrict to one file
  testrisk --json                           # Machine-readable report
  testrisk --prompt                         # Agent task from the evidence
  testrisk --fail-under-changed 95          # CI gate on changed-line coverage
  testrisk --doctor                         # Check coverage data and git
  python -m testrisk --version              # If testrisk is not on PATH
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
        action="store_true",
        help="Only show gaps that intersect git-changed lines",
    )
    parser.add_argument(
        "--base",
        default=None,
        metavar="REF",
        help="Git ref to diff against (default: origin/main, then main, master, HEAD)",
    )
    parser.add_argument(
        "--top",
        "-n",
        type=int,
        default=10,
        metavar="N",
        help="How many gaps to show (default: 10; 0 means all)",
    )
    parser.add_argument(
        "--file",
        "-f",
        dest="files",
        action="append",
        metavar="PATH",
        help="Restrict ranking to this source file (repeatable)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the report as JSON",
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Print an evidence-based task for an AI coding agent",
    )
    parser.add_argument(
        "--fail-under-changed",
        type=float,
        default=None,
        metavar="PCT",
        help="Exit 1 if changed-line coverage is below this percent",
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
    color = "never" if args.json or args.prompt else args.color
    configure_ui(color=color, quiet=bool(args.quiet and not args.json and not args.prompt))
    ui = get_ui()

    if args.top < 0:
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
        report = analyze(
            root=repo_path,
            coverage=args.coverage,
            changed_only=args.changed,
            base=args.base,
            files=tuple(args.files or ()),
            top=args.top,
        )
    except GapError as exc:
        if args.json:
            print(json.dumps({"error": str(exc).split("\n", 1)[0]}))
            return 1
        ui.error(str(exc))
        return 1

    if args.json:
        render_json(report, prompt=args.prompt)
    elif args.prompt:
        render_prompt(report)
    elif args.quiet:
        if report.suggested_target is not None:
            print(report.suggested_target.as_posix())
        elif report.gaps:
            print(report.gaps[0].suggested_test.as_posix())
    else:
        render_text(report)

    if args.fail_under_changed is not None:
        return _check_changed_floor(report.changed, args.fail_under_changed, args.json)
    return 0


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
