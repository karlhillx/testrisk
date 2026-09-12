"""Stable public library surface."""

import testgap


def test_public_exports():
    assert set(testgap.__all__) == {
        "Gap",
        "GapError",
        "GapReport",
        "Options",
        "Risk",
        "__version__",
        "analyze",
        "find_repo_root",
    }
    for name in testgap.__all__:
        assert getattr(testgap, name) is not None


def test_gap_error_is_usable():
    from testgap import GapError

    assert issubclass(GapError, Exception)
    try:
        raise GapError("no coverage data found")
    except GapError as exc:
        assert "coverage" in str(exc)
