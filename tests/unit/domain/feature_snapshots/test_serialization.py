from datetime import UTC, datetime
from decimal import Decimal

import pytest

from auto_trading_v2.domain.feature_snapshots import (
    FeatureSnapshotValidationError,
    canonical_json,
)
from tests.unit.domain.feature_snapshots.helpers import snapshot_input


def test_nested_decimal_is_fixed_non_scientific_and_mapping_order_is_canonical() -> None:
    first = snapshot_input(
        feature_values={
            "z": [Decimal("1E+3"), {"ratio": Decimal("1.2300")}],
            "a": True,
        }
    )
    second = snapshot_input(
        feature_values={
            "a": True,
            "z": [Decimal("1000"), {"ratio": Decimal("1.23")}],
        }
    )

    assert canonical_json(first.feature_values) == '{"a":true,"z":["1000",{"ratio":"1.23"}]}'
    assert canonical_json(first.feature_values) == canonical_json(second.feature_values)


def test_decimal_canonicalization_preserves_precision_without_global_context() -> None:
    source = snapshot_input(
        feature_values={
            "value": Decimal("0.0084033613445378151260504201680672269"),
        }
    )

    assert source.feature_values["value"] == "0.0084033613445378151260504201680672269"


@pytest.mark.parametrize(
    "invalid",
    [
        {"value": 1.0},
        {"nested": [{"value": float("nan")}]},
        {"nested": {"value": float("inf")}},
        {"nested": {"value": float("-inf")}},
        {"value": Decimal("NaN")},
        {"value": Decimal("Infinity")},
        {"value": (1, 2)},
        {"value": {1, 2}},
        {"value": b"bytes"},
        {"value": datetime(2026, 7, 20, tzinfo=UTC)},
    ],
)
def test_unsupported_or_non_finite_values_are_rejected_at_any_depth(
    invalid: dict[str, object],
) -> None:
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(feature_values=invalid)


def test_non_string_nested_key_is_rejected() -> None:
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(feature_values={"nested": {1: "invalid"}})


@pytest.mark.parametrize(
    "forbidden_key",
    ["future_price", "outcome", "label", "recommendation", "prediction"],
)
def test_future_result_and_recommendation_fields_are_rejected(forbidden_key: str) -> None:
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(feature_values={"nested": {forbidden_key: 1}})
