"""Tests for terminal output helpers."""

from testrisk.ui import Ui, resolve_color


def test_ascii_symbols_when_unicode_off():
    ui = Ui(color=False, quiet=False, unicode=False)
    assert ui.ok == "ok"
    assert ui.fail == "fail"
    assert ui.warn_mark == "warn"


def test_unicode_symbols_when_enabled():
    ui = Ui(color=False, quiet=False, unicode=True)
    assert ui.ok == "✓"
    assert ui.fail == "✗"


def test_quiet_hides_info_but_not_errors(capsys):
    ui = Ui(color=False, quiet=True, unicode=False)
    ui.info("hidden")
    ui.error("shown")
    captured = capsys.readouterr()
    assert "hidden" not in captured.out
    assert "shown" in captured.err


def test_resolve_color_never_and_always(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert resolve_color("never") is False
    assert resolve_color("always") is True


def test_resolve_color_respects_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert resolve_color("auto") is False
