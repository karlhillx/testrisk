"""
Terminal output for the CLI.

Color follows ``--color`` / ``NO_COLOR`` / ``FORCE_COLOR``. Unicode symbols
are used on interactive terminals; CI and pipes get plain ASCII.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"


def resolve_color(choice: str) -> bool:
    """Resolve ``auto`` / ``always`` / ``never`` against the environment."""
    if choice == "always":
        return True
    if choice == "never":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(sys.stdout.isatty())


def resolve_unicode() -> bool:
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(sys.stdout.isatty())


@dataclass
class Ui:
    """Small helper so every banner uses the same voice."""

    color: bool = False
    quiet: bool = False
    unicode: bool = False

    @classmethod
    def from_env(cls, *, color: str = "auto", quiet: bool = False) -> Ui:
        return cls(
            color=resolve_color(color),
            quiet=quiet,
            unicode=resolve_unicode(),
        )

    @property
    def ok(self) -> str:
        return "✓" if self.unicode else "ok"

    @property
    def fail(self) -> str:
        return "✗" if self.unicode else "fail"

    @property
    def warn_mark(self) -> str:
        return "!" if self.unicode else "warn"

    def _paint(self, text: str, *codes: str) -> str:
        if not self.color or not codes:
            return text
        return f"{''.join(codes)}{text}{RESET}"

    def _write(self, msg: str, *, stream=None, persist: bool = False) -> None:
        if self.quiet and not persist:
            return
        print(msg, file=stream or sys.stdout, flush=True)

    def info(self, msg: str, *, persist: bool = False) -> None:
        self._write(msg, persist=persist)

    def note(self, msg: str, *, stream=None, persist: bool = False) -> None:
        self._write(self._paint(msg, DIM), stream=stream, persist=persist)

    def warn(self, msg: str) -> None:
        prefix = self._paint(self.warn_mark, YELLOW, BOLD)
        self._write(f"{prefix}  {msg}", stream=sys.stderr, persist=True)

    def error(self, msg: str) -> None:
        prefix = self._paint(self.fail, RED, BOLD)
        self._write(f"{prefix}  {msg}", stream=sys.stderr, persist=True)

    def success(self, msg: str, *, persist: bool = True) -> None:
        prefix = self._paint(self.ok, GREEN, BOLD)
        self._write(f"{prefix}  {msg}", persist=persist)

    def title(self, msg: str, *, persist: bool = False) -> None:
        self._write(self._paint(msg, BOLD, CYAN), persist=persist)

    def kv(self, key: str, value: str, *, persist: bool = False) -> None:
        label = self._paint(f"{key:<12}", DIM)
        self._write(f"  {label}{value}", persist=persist)

    def blank(self, *, persist: bool = False) -> None:
        self._write("", persist=persist)

    def risk(self, label: str) -> str:
        if label == "HIGH":
            return self._paint(label, RED, BOLD)
        if label == "MEDIUM":
            return self._paint(label, YELLOW, BOLD)
        return self._paint(label, DIM)


_ui: Ui | None = None


def configure_ui(*, color: str = "auto", quiet: bool = False, unicode: bool | None = None) -> Ui:
    global _ui
    _ui = Ui(
        color=resolve_color(color),
        quiet=quiet,
        unicode=resolve_unicode() if unicode is None else unicode,
    )
    return _ui


def get_ui() -> Ui:
    global _ui
    if _ui is None:
        _ui = Ui.from_env()
    return _ui
