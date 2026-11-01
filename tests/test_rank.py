"""Ranking weights and risk bands."""

from testrisk.models import Risk
from testrisk.rank import Weights, classify_risk, score_gap


def test_changed_uncovered_outweighs_raw_missing_lines():
    quiet, _, _ = score_gap(
        missing_lines=6,
        missing_branches=0,
        complexity=2,
        changed_uncovered=0,
        has_tests=True,
    )
    hot, risk, parts = score_gap(
        missing_lines=2,
        missing_branches=0,
        complexity=2,
        changed_uncovered=2,
        has_tests=True,
    )
    assert hot > quiet
    assert risk is Risk.MEDIUM
    assert parts.changed_uncovered == 6.0
    assert parts.total == hot


def test_high_risk_for_complex_uncovered_branches():
    value, risk, _ = score_gap(
        missing_lines=6,
        missing_branches=2,
        complexity=11,
        changed_uncovered=0,
        has_tests=True,
    )
    assert value >= 16
    assert risk is Risk.HIGH


def test_low_risk_for_tiny_covered_neighborhood():
    _value, risk, _ = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
    )
    assert risk is Risk.LOW


def test_missing_tests_add_a_flat_boost():
    with_tests, _, with_parts = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
    )
    without, _, without_parts = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=False,
    )
    assert without - with_tests == 4.0
    assert without_parts.no_tests == 4.0
    assert with_parts.no_tests == 0.0


def test_custom_weights_change_score():
    default, _, _ = score_gap(
        missing_lines=2,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
    )
    custom, _, parts = score_gap(
        missing_lines=2,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
        weights=Weights(missing_lines=3.0),
    )
    assert custom == 6.0
    assert custom > default
    assert parts.missing_lines == 6.0


def test_churn_and_fan_in_add_capped_score():
    quiet, _, quiet_parts = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
    )
    hot, _, parts = score_gap(
        missing_lines=1,
        missing_branches=0,
        complexity=1,
        changed_uncovered=0,
        has_tests=True,
        churn=20,
        fan_in=20,
    )
    assert parts.churn == 12 * 0.25
    assert parts.fan_in == 10 * 0.4
    assert hot - quiet == parts.churn + parts.fan_in
    assert quiet_parts.churn == 0.0


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
