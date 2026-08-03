from dataclasses import replace

import pytest

from auto_trading_v2.domain.training_readiness import (
    LegacyCalibrationReadiness,
    PercentageStatus,
    calculate_percentage,
    evaluate_legacy_calibration_readiness,
    included_dataset_facts,
)
from tests.unit.training_readiness_helpers import aggregate


def _ready_facts():
    aggregate_value = aggregate()
    value = included_dataset_facts(aggregate_value.dataset, aggregate_value.items)
    return replace(
        value,
        total_item_count=300,
        unique_source_session_count=60,
        retrospective_replay_item_count=150,
        retrospective_replay_source_session_count=20,
        prospective_item_count=150,
        prospective_source_session_count=20,
        positive_count=150,
        not_positive_count=150,
        replay_positive_count=75,
        replay_not_positive_count=75,
        prospective_positive_count=75,
        prospective_not_positive_count=75,
    )


def test_included_counts_integrity_and_invalid_order_or_digest() -> None:
    value = aggregate()
    facts = included_dataset_facts(value.dataset, value.items)
    reversed_facts = included_dataset_facts(value.dataset, tuple(reversed(value.items)))
    digest_facts = included_dataset_facts(
        replace(value.dataset, content_digest="f" * 64), value.items
    )

    assert facts.total_item_count == 2
    assert facts.unique_symbol_listing_count == 2
    assert (facts.positive_count, facts.not_positive_count) == (1, 1)
    assert facts.canonical_order_valid is True
    assert facts.item_content_digest_valid is True
    assert reversed_facts.canonical_order_valid is False
    assert digest_facts.item_content_digest_valid is False


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, LegacyCalibrationReadiness.DATA_READY),
        ({"total_item_count": 299}, LegacyCalibrationReadiness.DATA_INSUFFICIENT),
        ({"unique_source_session_count": 59}, LegacyCalibrationReadiness.DATA_INSUFFICIENT),
        ({"positive_count": 59}, LegacyCalibrationReadiness.CLASS_IMBALANCED),
        ({"not_positive_count": 59}, LegacyCalibrationReadiness.CLASS_IMBALANCED),
        ({"replay_positive_count": 29}, LegacyCalibrationReadiness.CLASS_IMBALANCED),
        ({"replay_not_positive_count": 29}, LegacyCalibrationReadiness.CLASS_IMBALANCED),
        ({"retrospective_replay_item_count": 149}, LegacyCalibrationReadiness.DATA_INSUFFICIENT),
        ({"prospective_item_count": 99}, LegacyCalibrationReadiness.PROSPECTIVE_INSUFFICIENT),
        (
            {"prospective_source_session_count": 19},
            LegacyCalibrationReadiness.PROSPECTIVE_INSUFFICIENT,
        ),
    ],
)
def test_exact_legacy_thresholds(changes: dict[str, int], expected: object) -> None:
    value = aggregate()
    result = evaluate_legacy_calibration_readiness(
        value.dataset, replace(_ready_facts(), **changes)
    )

    assert result.status is expected
    assert "executable" in result.limitation


def test_percentage_is_decimal_text_and_zero_denominator_is_explicit() -> None:
    third = calculate_percentage(1, 3)
    empty = calculate_percentage(0, 0)

    assert third.percentage == "33.333333"
    assert third.status is PercentageStatus.DERIVED
    assert empty.percentage is None
    assert empty.status is PercentageStatus.ZERO_DENOMINATOR
