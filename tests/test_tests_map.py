"""Test-file heuristics."""

from pathlib import Path

from helpers import write_sample_project

from testrisk.tests_map import is_test_path, iter_test_files, related_tests, suggested_test_path


def test_is_test_path():
    assert is_test_path(Path("tests/test_foo.py"))
    assert is_test_path(Path("test/test_foo.py"))
    assert is_test_path(Path("foo_test.py"))
    assert is_test_path(Path("conftest.py"))
    assert not is_test_path(Path("demo/services.py"))


def test_suggested_test_path():
    assert suggested_test_path(Path("demo/services.py")) == Path("tests/test_services.py")
    assert suggested_test_path(Path("src/pkg/foo.py")) == Path("tests/pkg/test_foo.py")
    assert suggested_test_path(Path("pkg/sub/mod.py")) == Path("tests/pkg/sub/test_mod.py")


def test_suggested_test_path_prefers_existing_flat(tmp_path):
    write_sample_project(tmp_path)
    from testrisk.tests_map import iter_test_files

    inventory = iter_test_files(tmp_path)
    assert suggested_test_path(Path("src/demo/services.py"), inventory=inventory) == Path(
        "tests/test_services.py"
    )


def test_related_tests_finds_function_mention(tmp_path):
    write_sample_project(tmp_path)
    hits = related_tests(tmp_path, Path("demo/services.py"), "parse_config")
    assert Path("tests/test_services.py") in hits


def test_related_tests_ignores_conventional_file_without_mention(tmp_path):
    write_sample_project(tmp_path)
    hits = related_tests(tmp_path, Path("demo/services.py"), "ServiceManager.start")
    assert hits == ()


def test_related_tests_requires_stem_for_common_names(tmp_path):
    write_sample_project(tmp_path)
    other = tmp_path / "tests" / "test_other.py"
    other.write_text("def test_start_helper():\n    assert True\n", encoding="utf-8")
    hits = related_tests(tmp_path, Path("demo/services.py"), "ServiceManager.start")
    assert hits == ()


def test_iter_test_files_skips_virtualenv(tmp_path):
    write_sample_project(tmp_path)
    hidden = tmp_path / ".venv" / "lib" / "site-packages" / "tests" / "test_dep.py"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("def test_dep():\n    pass\n", encoding="utf-8")
    found = iter_test_files(tmp_path)
    assert Path("tests/test_services.py") in found
    assert all(".venv" not in path.parts for path in found)
