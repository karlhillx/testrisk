"""Human, JSON, and agent-prompt renderers."""

from __future__ import annotations

import json

from .models import Gap, GapReport, format_line_ranges
from .ui import get_ui
from .version import __version__


def render_text(report: GapReport) -> None:
    ui = get_ui()
    ui.title(f"testrisk {report.version or __version__}", persist=True)
    ui.blank(persist=True)
    ui.info(f"Coverage   {_pct(report.coverage.line_percent)}", persist=True)
    if report.coverage.branch_percent is not None:
        ui.info(f"Branch     {_pct(report.coverage.branch_percent)}", persist=True)
    ui.blank(persist=True)

    if report.gaps:
        ui.info("Highest-value test gaps", persist=True)
        ui.blank(persist=True)
        for index, gap in enumerate(report.gaps, start=1):
            _render_gap(gap, index)
            ui.blank(persist=True)
    else:
        ui.success("No test gaps found.")
        ui.blank(persist=True)

    if report.changed is not None:
        ui.info("Changed code", persist=True)
        if report.changed.statements == 0:
            ui.info("  No changed executable lines", persist=True)
        else:
            ui.info(f"  {_pct(report.changed.percent or 0.0)} covered", persist=True)
            missing = report.changed.statements - report.changed.covered
            noun = "line" if missing == 1 else "lines"
            ui.info(f"  {missing} uncovered executable {noun}", persist=True)
        ui.blank(persist=True)

    if report.suggested_target is not None:
        ui.info("Suggested next target:", persist=True)
        ui.info(f"  {report.suggested_target.as_posix()}", persist=True)


def _render_gap(gap: Gap, index: int) -> None:
    ui = get_ui()
    ui.info(f"  {index}. {gap.qualname}", persist=True)
    if gap.missing_lines:
        ui.info(f"     Missing: {format_line_ranges(gap.missing_lines)}", persist=True)
    if gap.missing_branches:
        count = len(gap.missing_branches)
        ui.info(f"     Branches: {count} uncovered", persist=True)
    ui.info(f"     Complexity: {gap.complexity}", persist=True)
    ui.info(f"     Risk: {ui.risk(gap.risk.value)}", persist=True)


def render_json(report: GapReport, *, prompt: bool = False) -> None:
    payload = report.to_dict()
    if prompt:
        payload["prompt"] = build_prompt(report)
    print(json.dumps(payload, indent=2))


def render_prompt(report: GapReport) -> None:
    print(build_prompt(report))


def build_prompt(report: GapReport) -> str:
    if not report.gaps:
        return (
            "No uncovered production behavior was ranked.\n"
            "Coverage looks complete for the selected scope."
        )
    blocks = [_prompt_block(gap) for gap in report.gaps]
    header = (
        "Write focused unit tests for these uncovered behaviors.\n"
        "\n"
        "Do not modify production code unless required to expose a testable seam."
    )
    return header + "\n\n" + "\n\n".join(blocks)


def _prompt_block(gap: Gap) -> str:
    lines = [
        f"Target:\n{gap.qualname}",
        "",
        f"Uncovered:\n{format_line_ranges(gap.missing_lines) or '(branches only)'}",
    ]
    if gap.missing_branches:
        lines.extend(
            [
                "",
                "Untested branches:",
                *[branch.describe() for branch in gap.missing_branches],
            ]
        )
    if gap.changed_uncovered:
        lines.extend(
            [
                "",
                f"Changed uncovered:\n{format_line_ranges(gap.changed_uncovered)}",
            ]
        )
    lines.extend(
        [
            "",
            f"Complexity: {gap.complexity}",
            f"Risk: {gap.risk.value}",
            "",
            "Existing tests:",
        ]
    )
    if gap.existing_tests:
        lines.extend(path.as_posix() for path in gap.existing_tests)
    else:
        lines.append(f"{gap.suggested_test.as_posix()} (does not exist yet)")
    return "\n".join(lines)


def _pct(value: float) -> str:
    return f"{value:.1f}%"
