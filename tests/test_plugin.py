"""Pytest --testrisk plugin."""

pytest_plugins = ["pytester"]


def test_testrisk_option_is_registered(pytester):
    config = pytester.parseconfig("--testrisk", "--testrisk-explain")
    assert config.getoption("testrisk") is True
    assert config.getoption("testrisk_explain") is True


def test_testrisk_terminal_summary_without_coverage(pytester):
    pytester.makepyfile(
        """
        def test_ok():
            assert True
        """
    )
    result = pytester.runpytest("--testrisk", "-q")
    result.stdout.fnmatch_lines(["*testrisk*"])
    assert result.ret == 0
