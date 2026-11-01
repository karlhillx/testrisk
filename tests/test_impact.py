"""Import fan-in."""

from pathlib import Path

from testrisk.impact import fan_in_counts


def test_fan_in_counts_importers(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "api.py").write_text("from pkg.core import VALUE\n", encoding="utf-8")
    (tmp_path / "pkg" / "cli.py").write_text("from . import core\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text(
        "from pkg.core import VALUE\n",
        encoding="utf-8",
    )
    counts = fan_in_counts(tmp_path)
    assert counts[Path("pkg/core.py")] == 2
