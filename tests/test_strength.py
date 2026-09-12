"""Ceremonial vs meaningful related-test checks."""

from testrisk.strength import (
    NEVER_CALLED,
    NO_ASSERTIONS,
    TAUTOLOGY,
    inspect_test_strength,
)


def test_meaningful_equality_assert():
    source = (
        "from demo.services import parse_config\n\n"
        "def test_parse_config_empty():\n"
        "    assert parse_config(None) == {}\n"
    )
    result = inspect_test_strength(source, "parse_config")
    assert result.meaningful is True
    assert result.reasons == ()


def test_pytest_raises_is_meaningful():
    source = (
        "import pytest\n"
        "from demo.services import parse_config\n\n"
        "def test_parse_config_missing():\n"
        "    with pytest.raises(ValueError):\n"
        "        parse_config({'x': 1})\n"
    )
    assert inspect_test_strength(source, "parse_config").meaningful is True


def test_assert_true_is_weak():
    source = (
        "from demo.services import ServiceManager\n\n"
        "def test_start_smoke():\n"
        "    ServiceManager().start('x')\n"
        "    assert True\n"
    )
    result = inspect_test_strength(source, "ServiceManager.start")
    assert result.meaningful is False
    assert TAUTOLOGY in result.reasons


def test_no_assertions_is_weak():
    source = (
        "from demo.services import parse_config\n\n"
        "def test_parse_config_runs():\n"
        "    parse_config(None)\n"
    )
    result = inspect_test_strength(source, "parse_config")
    assert result.meaningful is False
    assert NO_ASSERTIONS in result.reasons


def test_import_only_is_weak():
    source = "from demo.services import parse_config\n\ndef test_unrelated():\n    assert 1 == 1\n"
    result = inspect_test_strength(source, "parse_config")
    assert result.meaningful is False
    assert NEVER_CALLED in result.reasons
    assert NO_ASSERTIONS in result.reasons


def test_unreadable_is_not_penalized():
    result = inspect_test_strength("def (\n", "parse_config")
    assert result.meaningful is True


def test_assert_is_not_none_is_weak():
    source = (
        "from demo.services import parse_config\n\n"
        "def test_parse_config_exists():\n"
        "    result = parse_config(None)\n"
        "    assert result is not None\n"
    )
    result = inspect_test_strength(source, "parse_config")
    assert result.meaningful is False
    assert TAUTOLOGY in result.reasons
