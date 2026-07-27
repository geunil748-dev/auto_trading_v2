from datetime import UTC, datetime, timedelta

import pytest

from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshotValidationError,
    TradingDayHorizon,
)
from tests.unit.domain.feature_snapshots.helpers import AS_OF, provenance, snapshot_input


@pytest.mark.parametrize("value", [1, 5])
def test_horizon_accepts_only_bounded_trading_days(value: int) -> None:
    horizon = TradingDayHorizon(value)

    assert horizon.value == value
    assert horizon.unit == "TRADING_DAY"


@pytest.mark.parametrize("value", [0, 6])
def test_horizon_rejects_out_of_range_values(value: int) -> None:
    with pytest.raises(FeatureSnapshotValidationError):
        TradingDayHorizon(value)


def test_naive_cutoff_and_provenance_timestamps_are_rejected() -> None:
    naive = datetime(2026, 7, 20, 15)

    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(as_of=naive)
    with pytest.raises(FeatureSnapshotValidationError):
        provenance(observed_at=naive)
    with pytest.raises(FeatureSnapshotValidationError):
        provenance(available_at=naive)
    with pytest.raises(FeatureSnapshotValidationError):
        FeatureProvenanceEntry(
            source_code="TEST",
            source_record_key="row",
            observed_at=AS_OF,
            available_at=None,  # type: ignore[arg-type]
            content_digest="a" * 64,
        )


def test_observation_cannot_follow_availability() -> None:
    with pytest.raises(FeatureSnapshotValidationError):
        provenance(observed_at=AS_OF, available_at=AS_OF - timedelta(seconds=1))


def test_input_available_after_cutoff_rejects_entire_snapshot() -> None:
    future = provenance(
        observed_at=AS_OF,
        available_at=AS_OF + timedelta(microseconds=1),
    )

    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(entries=(future,))


def test_equality_across_point_in_time_boundaries_is_allowed() -> None:
    value = snapshot_input(entries=(provenance(observed_at=AS_OF, available_at=AS_OF),))

    assert value.latest_input_available_at == AS_OF
    assert value.as_of.tzinfo is UTC


def test_empty_features_and_provenance_are_rejected() -> None:
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(feature_values={})
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(entries=())


def test_duplicate_provenance_identity_is_rejected() -> None:
    duplicate = provenance()

    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(entries=(duplicate, duplicate))


def test_provenance_rejects_non_opaque_record_keys() -> None:
    with pytest.raises(FeatureSnapshotValidationError):
        provenance("source:record/key")


def test_quality_contract_has_no_persistable_blocked_state() -> None:
    assert set(FeatureQualityStatus) == {
        FeatureQualityStatus.READY,
        FeatureQualityStatus.DEGRADED,
    }
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(
            quality_status=FeatureQualityStatus.READY,
            quality_reason_codes=("SOURCE_DELAYED",),
        )
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(quality_status=FeatureQualityStatus.DEGRADED)


def test_degraded_reasons_are_unique_and_canonically_sorted() -> None:
    value = snapshot_input(
        quality_status=FeatureQualityStatus.DEGRADED,
        quality_reason_codes=("VOLUME_DELAYED", "PRICE_DELAYED"),
    )

    assert value.quality_reason_codes == ("PRICE_DELAYED", "VOLUME_DELAYED")
    with pytest.raises(FeatureSnapshotValidationError):
        snapshot_input(
            quality_status=FeatureQualityStatus.DEGRADED,
            quality_reason_codes=("PRICE_DELAYED", "PRICE_DELAYED"),
        )


def test_timezone_offsets_are_normalized_to_utc() -> None:
    offset = datetime.fromisoformat("2026-07-21T00:00:00+09:00")
    entry = FeatureProvenanceEntry(
        source_code="TEST",
        source_record_key="row",
        observed_at=offset,
        available_at=offset,
        content_digest="b" * 64,
    )

    assert entry.observed_at == AS_OF
