"""JSON, XML, and .coverage loaders."""

from pathlib import Path

from coverage import Coverage
from helpers import write_coverage_json, write_sample_project

from testrisk.coverage_data import load_coverage
from testrisk.models import format_line_ranges


def test_format_line_ranges():
    assert format_line_ranges((84, 85, 86, 103)) == "84-86, 103"
    assert format_line_ranges(()) == ""
    assert format_line_ranges((7,)) == "7"


def test_load_json(tmp_path):
    write_sample_project(tmp_path)
    write_coverage_json(
        tmp_path,
        missing_lines=[8, 9],
        executed_lines=[1, 2, 3, 4, 5],
        missing_branches=[[4, 0], [8, -1]],
        line_percent=91.7,
        branch_percent=84.2,
        contexts={"5": ["tests/test_services.py::test_parse_config_empty"]},
    )
    snap = load_coverage(tmp_path, tmp_path / "coverage.json")
    assert round(snap.line_percent, 1) == 91.7
    assert round(snap.branch_percent or 0, 1) == 84.2
    file_cov = snap.files[0]
    assert file_cov.path == Path("demo/services.py")
    assert file_cov.missing_lines == frozenset({8, 9})
    assert file_cov.missing_branches[0].describe() == "line 4: false branch"
    assert file_cov.missing_branches[1].describe() == "line 8: exception/exit branch"
    assert file_cov.has_contexts
    assert file_cov.contexts[5] == ("tests/test_services.py::test_parse_config_empty",)


def test_load_xml(tmp_path):
    write_sample_project(tmp_path)
    xml = f"""<?xml version="1.0" ?>
<coverage line-rate="0.8" branch-rate="0.5" lines-valid="5" lines-covered="4"
          branches-valid="2" branches-covered="1">
  <sources><source>{tmp_path}</source></sources>
  <packages>
    <package name="demo">
      <classes>
        <class filename="demo/services.py">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="1"/>
            <line number="8" hits="0"/>
            <line number="4" hits="1" branch="true" condition-coverage="50% (1/2)"
                  missing-branches="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""
    path = tmp_path / "coverage.xml"
    path.write_text(xml, encoding="utf-8")
    snap = load_coverage(tmp_path, path)
    assert snap.line_percent == 80.0
    assert snap.branch_percent == 50.0
    file_cov = snap.files[0]
    assert 8 in file_cov.missing_lines
    assert file_cov.missing_branches[0].dest == 0


def test_load_coverage_db(tmp_path):
    write_sample_project(tmp_path)
    source = tmp_path / "demo" / "services.py"
    data_file = tmp_path / ".coverage"
    cov = Coverage(data_file=str(data_file), source=[str(tmp_path / "demo")])
    cov.start()
    import importlib.util

    spec = importlib.util.spec_from_file_location("demo.services", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.parse_config(None)
    cov.stop()
    cov.save()
    snap = load_coverage(tmp_path, data_file)
    assert snap.statements > 0
    assert snap.files
    missing = next(item for item in snap.files if item.path.name == "services.py")
    assert missing.missing_lines
