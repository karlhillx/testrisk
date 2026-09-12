"""
testrisk — find the code most likely to need better tests.

Reads coverage.py data, maps uncovered lines onto functions via the AST,
weights git-changed code and missing tests, and prints a prioritized list::

    from testrisk import GapError, analyze

    report = analyze(".")
    for gap in report.gaps:
        print(gap.qualname, gap.risk)
"""

from .discover import find_repo_root
from .engine import Options, analyze
from .errors import GapError
from .models import Gap, GapReport, Risk
from .version import __version__

__author__ = "Karl Hill"
__license__ = "MIT"

__all__ = [
    "Gap",
    "GapError",
    "GapReport",
    "Options",
    "Risk",
    "__version__",
    "analyze",
    "find_repo_root",
]
