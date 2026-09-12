"""Ranking weights and risk bands."""

from testgap.models import Risk
from testgap.rank import classify_risk, score_gap


def test_changed_uncovered_outweighs_raw_missing_lines():
    quiet, _ = score_gap(
        missing_lines=6,
        missing_branches=0,
        complexity=2,
        changed_uncovered=0,
        has_tests=True,
    )
    hot, risk = score_gap(
        missing_lines=2,
        missing_branches=0,
        complexity=2,
        changed_uncovered=2,
        has_tests=True,
    )
    assert hot > quiet
    assert risk is Risk.MEDIUM


def test_high_risk_for_complex_uncovered_branches():
    value, risk = score_gap(
        missing_lines=6,
        missing_branches=2,
        complexity=11,
        changed_uncovered=0,
        has_tests=True,
    )
    assert value >= 16
    assert risk is Risk.HIGH


def test_low_risk_for_tiny_covered_neighborhood():
    _value, risk = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
    )
    assert risk is Risk.LOW


def test_missing_tests_add_a_flat_boost():
    with_tests, _ = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
    )
    without, _ = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=False,
    )
    assert without - with_tests == 4.0


def test_classify_risk_changed_threshold():
    assert (
        classify_risk(
            value=3,
            complexity=2,
            missing_branches=0,
            changed_uncovered=5,
            missing_lines=5,
        )
        is Risk.HIGH
    )
