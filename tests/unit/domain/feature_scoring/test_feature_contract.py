from copy import deepcopy
from decimal import Decimal

import pytest

from auto_trading_v2.domain.feature_scoring import (
    FeatureScoringValidationError,
    parse_v1_technical_features,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus

from .helpers import feature_values, snapshot, snapshot_like


def test_exact_v1_ready_payload_parses_canonical_decimal_strings() -> None:
    parsed = parse_v1_technical_features(snapshot())

    assert parsed.values["last_close"] == Decimal("100")
    assert parsed.values["one_day_return"] == Decimal("1")
    assert parsed.values["average_dollar_volume_20"] == Decimal("1")


@pytest.mark.parametrize("value", [1.5, "NaN", "Infinity", "1e-3", Decimal("1")])
def test_unknown_numeric_representation_is_rejected(value: object) -> None:
    values = feature_values()
    values["one_day_return"] = value

    with pytest.raises(FeatureScoringValidationError, match="FEATURE_NUMERIC_VALUE_INVALID"):
        parse_v1_technical_features(snapshot_like(values))  # type: ignore[arg-type]


def test_raw_invalid_payload_is_not_echoed() -> None:
    raw = "credential-like-private-feature-payload"
    values = feature_values()
    values["five_day_return"] = raw

    with pytest.raises(FeatureScoringValidationError) as caught:
        parse_v1_technical_features(snapshot_like(values))  # type: ignore[arg-type]

    assert raw not in str(caught.value)


@pytest.mark.parametrize(
    ("mutation", "category"),
    [
        (lambda values: values.pop("last_close"), "FEATURE_KEY_CONTRACT_INVALID"),
        (
            lambda values: values.__setitem__("adjustment_basis", "RAW"),
            "FEATURE_ADJUSTMENT_BASIS_INVALID",
        ),
        (
            lambda values: values.__setitem__("completed_bar_count", 20),
            "FEATURE_COMPLETED_BAR_COUNT_INVALID",
        ),
    ],
)
def test_reference_contract_drift_is_rejected(mutation: object, category: str) -> None:
    values = feature_values()
    mutation(values)  # type: ignore[operator]

    with pytest.raises(FeatureScoringValidationError, match=category):
        parse_v1_technical_features(snapshot_like(values))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("code", "version", "category"),
    [
        ("OTHER", "v1", "FEATURE_SET_CODE_MISMATCH"),
        ("US_EQUITY_DAILY_TECHNICAL", "v2", "FEATURE_SET_VERSION_MISMATCH"),
    ],
)
def test_feature_set_identity_is_exact(code: str, version: str, category: str) -> None:
    with pytest.raises(FeatureScoringValidationError, match=category):
        parse_v1_technical_features(
            snapshot_like(feature_values(), feature_set_code=code, feature_set_version=version)
        )  # type: ignore[arg-type]


def test_ready_requires_all_volume_features() -> None:
    values = feature_values()
    values["volume_ratio_5_to_20"] = None

    with pytest.raises(FeatureScoringValidationError, match="FEATURE_READY_VOLUME_INCOMPLETE"):
        parse_v1_technical_features(snapshot_like(values))  # type: ignore[arg-type]


@pytest.mark.parametrize("reason", ["VOLUME_DATA_INCOMPLETE", "VOLUME_DATA_UNUSABLE"])
def test_known_degraded_volume_reason_is_allowed(reason: str) -> None:
    values = feature_values(volume=None)
    parsed = parse_v1_technical_features(
        snapshot_like(
            values,
            quality=FeatureQualityStatus.DEGRADED,
            reasons=(reason,),
        )  # type: ignore[arg-type]
    )

    assert all(
        key not in parsed.values
        for key in values
        if key.startswith("volume_")
        or key.startswith("latest_volume")
        or key.startswith("average_dollar")
    )


def test_unknown_degraded_reason_is_rejected() -> None:
    with pytest.raises(FeatureScoringValidationError, match="FEATURE_QUALITY_UNSUPPORTED"):
        parse_v1_technical_features(
            snapshot_like(
                deepcopy(feature_values(volume=None)),
                quality=FeatureQualityStatus.DEGRADED,
                reasons=("OTHER_REASON",),
            )  # type: ignore[arg-type]
        )
