"""Pytest plugin: ``pytest --cov --testrisk`` ranks gaps after the suite."""

from __future__ import annotations

from pathlib import Path

from .engine import Options, analyze
from .errors import GapError
from .report import render_text
from .ui import configure_ui


def pytest_addoption(parser) -> None:
    group = parser.getgroup("testrisk")
    group.addoption(
        "--testrisk",
        action="store_true",
        default=False,
        help="Rank test gaps after the run (reads coverage.json or .coverage)",
    )
    group.addoption(
        "--testrisk-all",
        action="store_true",
        default=False,
        help="With --testrisk, rank the whole tree instead of --changed",
    )
    group.addoption(
        "--testrisk-explain",
        action="store_true",
        default=False,
        help="With --testrisk, show the score breakdown",
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    if not config.getoption("testrisk"):
        return
    root = Path(config.rootpath)
    configure_ui(color="auto", quiet=False)
    try:
        report = analyze(
            options=Options(
                root=root,
                changed_only=not config.getoption("testrisk_all"),
                apply_config=True,
            )
        )
    except GapError as exc:
        terminalreporter.write_sep("=", "testrisk")
        terminalreporter.write_line(str(exc).split("\n", 1)[0])
        return
    terminalreporter.write_sep("=", "testrisk")
    render_text(report, explain=bool(config.getoption("testrisk_explain")))
