"""Human, JSON, and agent-prompt renderers."""

from __future__ import annotations

import json
from pathlib import Path

from .discover import GENERATE_COVERAGE, RANK_CHANGED
from .models import (
    Gap,
    GapReport,
    ScoreParts,
    TestKind,
    Totals,
    format_line_ranges,
    totals_from_gaps,
)
from .strength import REASON_LABELS
from .ui import get_ui
from .version import __version__

_EXCERPT_LIMIT = 40
_EXCERPT_CONTEXT = 1


def render_text(report: GapReport, *, explain: bool = False) -> None:
    ui = get_ui()
    ui.title(f"testrisk {report.version or __version__}", persist=True)
    ui.blank(persist=True)
    ui.kv("Coverage", _coverage_summary(report), persist=True)
    if report.changed is not None:
        ui.kv("Changed", _changed_summary(report), persist=True)
    if report.stale_coverage:
        ui.kv("Stale", f"coverage older than changed files — {GENERATE_COVERAGE}", persist=True)
    if report.has_contexts:
        ui.kv("Contexts", "coverage test contexts (pytest --cov-context=test)", persist=True)
    if report.waived:
        ui.kv("Waived", f"{len(report.waived)} baseline gap(s) omitted from gates", persist=True)
    ui.blank(persist=True)

    if report.gaps:
        ui.info("Highest-value test gaps", persist=True)
        ui.blank(persist=True)
        for index, gap in enumerate(report.gaps, start=1):
            if index > 1:
                ui.blank(persist=True)
                ui.rule(persist=True)
                ui.blank(persist=True)
            _render_gap(gap, index, explain=explain)
    else:
        ui.success("No test gaps found.")

    if report.suggested_target is not None or report.gaps:
        ui.blank(persist=True)
        ui.rule(persist=True)
        ui.blank(persist=True)
        _render_footer(report)


def _render_gap(gap: Gap, index: int, *, explain: bool) -> None:
    ui = get_ui()
    ui.info(f"  {index}. {gap.qualname}", persist=True)
    ui.row("risk", f"{ui.risk(gap.risk.value)}  ·  {gap.score:.1f}", persist=True)
    missing = format_line_ranges(gap.missing_lines) or "(branches only)"
    if gap.missing_branches:
        noun = "branch" if len(gap.missing_branches) == 1 else "branches"
        missing = f"{missing}  ·  {len(gap.missing_branches)} {noun}"
    ui.row("missing", missing, persist=True)
    if gap.changed_uncovered:
        ui.row("changed", format_line_ranges(gap.changed_uncovered), persist=True)
    ui.row("tests", _tests_label(gap), persist=True)
    if gap.executed_by:
        ui.row("ran", ", ".join(gap.executed_by[:3]), persist=True)
    if gap.weak_reasons:
        ui.row("weak", _weak_label(gap), persist=True)
    if explain:
        why = _why_label(gap.score_parts)
        if why:
            ui.row("why", why, persist=True)


def _tests_label(gap: Gap) -> str:
    if gap.kind is TestKind.INDIRECT:
        return f"indirect → {gap.suggested_test.as_posix()}"
    if gap.existing_tests:
        return ", ".join(path.as_posix() for path in gap.existing_tests[:3])
    return f"none → {gap.suggested_test.as_posix()}"


def _weak_label(gap: Gap) -> str:
    return ", ".join(
        REASON_LABELS.get(reason, reason.replace("_", " ")) for reason in gap.weak_reasons
    )


def _why_label(parts: ScoreParts) -> str:
    bits: list[str] = []
    if parts.missing_lines:
        bits.append(f"lines {parts.missing_lines:.1f}")
    if parts.missing_branches:
        bits.append(f"branches {parts.missing_branches:.1f}")
    if parts.complexity:
        bits.append(f"complexity {parts.complexity:.1f}")
    if parts.changed_uncovered:
        bits.append(f"changed {parts.changed_uncovered:.1f}")
    if parts.no_tests:
        bits.append(f"no tests {parts.no_tests:.1f}")
    if parts.churn:
        bits.append(f"churn {parts.churn:.1f}")
    if parts.fan_in:
        bits.append(f"fan-in {parts.fan_in:.1f}")
    return "  ·  ".join(bits)


def _render_footer(report: GapReport) -> None:
    ui = get_ui()
    totals = report.totals if report.totals.matched else totals_from_gaps(report.gaps)
    if report.suggested_target is not None:
        ui.kv("Next", report.suggested_target.as_posix(), persist=True)
    if totals.matched:
        ui.kv("Shown", _shown_label(totals), persist=True)
        ui.kv("Risk", _risk_totals(totals), persist=True)
        ui.kv("Checks", _check_totals(totals), persist=True)
        ui.kv("Hint", _hint(report, totals), persist=True)
        nudge = _changed_nudge(report, totals)
        if nudge:
            ui.kv("Scope", nudge, persist=True)


def _shown_label(totals: Totals) -> str:
    noun = "gap" if totals.matched == 1 else "gaps"
    if totals.shown < totals.matched:
        return f"{totals.shown} of {totals.matched} {noun}"
    return f"{totals.matched} {noun}"


def _risk_totals(totals: Totals) -> str:
    return f"{totals.high} HIGH  ·  {totals.medium} MEDIUM  ·  {totals.low} LOW"


def _check_totals(totals: Totals) -> str:
    return (
        f"{totals.none} none  ·  {totals.indirect} indirect  ·  "
        f"{totals.weak} weak  ·  {totals.meaningful} meaningful"
    )


def _hint(report: GapReport, totals: Totals) -> str:
    if totals.high:
        lead = "Start with the top HIGH gap."
    elif report.gaps:
        lead = "Start with the top gap."
    else:
        lead = "No ranked gaps in this scope."
    return f"{lead} Score favors changed uncovered lines and tests that cannot fail."


def _changed_nudge(report: GapReport, totals: Totals) -> str:
    if report.changed_only or totals.matched <= 10:
        return ""
    noun = "gap" if totals.matched == 1 else "gaps"
    return f"{totals.matched} {noun}; re-run with {RANK_CHANGED} to focus this branch."


def _coverage_summary(report: GapReport) -> str:
    line = _pct(report.coverage.line_percent)
    if report.coverage.branch_percent is None:
        return line
    return f"{line}   Branch {_pct(report.coverage.branch_percent)}"


def _changed_summary(report: GapReport) -> str:
    changed = report.changed
    if changed is None or changed.statements == 0:
        return "no changed executable lines"
    missing = changed.statements - changed.covered
    noun = "line" if missing == 1 else "lines"
    return f"{_pct(changed.percent or 0.0)} covered   {missing} uncovered {noun}"


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
    blocks = [_prompt_block(report, gap) for gap in report.gaps]
    header = (
        "Write focused unit tests for these uncovered behaviors.\n"
        "\n"
        "Do not modify production code unless required to expose a testable seam."
    )
    return header + "\n\n" + "\n\n".join(blocks)


def _prompt_block(report: GapReport, gap: Gap) -> str:
    lines = [
        f"Target:\n{gap.qualname}",
        "",
        f"Uncovered:\n{format_line_ranges(gap.missing_lines) or '(branches only)'}",
    ]
    excerpt = source_excerpt(report.root, gap)
    if excerpt:
        lines.extend(["", "Source:", excerpt])
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
    if gap.executed_by:
        lines.extend(["", "Tests that already execute this function:", *gap.executed_by])
    lines.extend(
        [
            "",
            f"Complexity: {gap.complexity}",
            f"Score: {gap.score:.1f}",
            f"Risk: {gap.risk.value}",
            "",
            "Existing tests:",
        ]
    )
    if gap.kind is TestKind.INDIRECT:
        lines.append(f"{gap.suggested_test.as_posix()} (no mention of this function yet)")
    elif gap.existing_tests:
        lines.extend(path.as_posix() for path in gap.existing_tests)
        if gap.weak_reasons:
            lines.extend(
                [
                    "",
                    "Weak checks:",
                    *[
                        f"- {REASON_LABELS.get(reason, reason.replace('_', ' '))}"
                        for reason in gap.weak_reasons
                    ],
                    "",
                    "Write assertions that fail if the uncovered behavior is wrong.",
                    "Do not add assert True or smoke tests that only prove",
                    "the function is callable.",
                ]
            )
    elif (report.root / gap.suggested_test).is_file():
        lines.append(f"{gap.suggested_test.as_posix()} (no mention of this function yet)")
    else:
        lines.append(f"{gap.suggested_test.as_posix()} (does not exist yet)")
    return "\n".join(lines)


def source_excerpt(
    root: Path,
    gap: Gap,
    *,
    context: int = _EXCERPT_CONTEXT,
    limit: int = _EXCERPT_LIMIT,
) -> str:
    """Numbered source lines covering the gap, or ``""`` if unavailable."""
    path = root / gap.path
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    source_lines = text.splitlines()
    wanted: set[int] = set()
    for number in (*gap.missing_lines, *(branch.line for branch in gap.missing_branches)):
        for candidate in range(number - context, number + context + 1):
            if 1 <= candidate <= len(source_lines):
                wanted.add(candidate)
    if not wanted:
        return ""
    ordered = _fill_small_holes(sorted(wanted))
    if len(ordered) > limit:
        ordered = ordered[:limit]
        truncated = True
    else:
        truncated = False
    width = len(str(ordered[-1]))
    rows = [f"{number:>{width}} | {source_lines[number - 1]}" for number in ordered]
    if truncated:
        rows.append(f"{'':>{width}} | ...")
    return "\n".join(rows)


def _fill_small_holes(ordered: list[int], max_hole: int = 2) -> list[int]:
    """Keep short gaps in an excerpt so ``try:`` / blanks are not dropped."""
    if not ordered:
        return ordered
    filled = [ordered[0]]
    for number in ordered[1:]:
        prev = filled[-1]
        if 1 < number - prev <= max_hole + 1:
            filled.extend(range(prev + 1, number))
        filled.append(number)
    return filled


def _pct(value: float) -> str:
    return f"{value:.1f}%"
