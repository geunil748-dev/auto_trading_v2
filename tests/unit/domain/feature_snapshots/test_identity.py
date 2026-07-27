from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from auto_trading_v2.domain.feature_snapshots import (
    FeatureQualityStatus,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives import Symbol
from tests.unit.domain.feature_snapshots.helpers import AS_OF, provenance, snapshot_input


def test_same_semantic_identity_always_has_same_key() -> None:
    first = snapshot_input(feature_values={"value": 1})
    second = snapshot_input(
        feature_values={"value": 2},
        quality_status=FeatureQualityStatus.DEGRADED,
        quality_reason_codes=("SOURCE_DELAYED",),
    )

    assert feature_snapshot_key(first) == feature_snapshot_key(second)
    assert feature_content_digest(first) != feature_content_digest(second)


def test_mapping_and_provenance_order_do_not_change_content_digest() -> None:
    earlier = provenance(
        "row-a",
        observed_at=AS_OF - timedelta(minutes=2),
        available_at=AS_OF - timedelta(minutes=1),
        digest_character="a",
    )
    later = provenance("row-b", digest_character="b")
    first = snapshot_input(
        feature_values={"b": 2, "a": {"y": Decimal("2.0"), "x": 1}},
        entries=(later, earlier),
    )
    second = snapshot_input(
        feature_values={"a": {"x": 1, "y": Decimal("2")}, "b": 2},
        entries=(earlier, later),
    )

    assert feature_snapshot_key(first) == feature_snapshot_key(second)
    assert feature_content_digest(first) == feature_content_digest(second)
    assert first.latest_input_available_at == AS_OF


def test_content_change_changes_digest_but_not_key() -> None:
    first = snapshot_input(feature_values={"value": 1})
    second = snapshot_input(feature_values={"value": 2})

    assert feature_snapshot_key(first) == feature_snapshot_key(second)
    assert feature_content_digest(first) != feature_content_digest(second)


def test_same_content_with_different_identity_is_a_separate_snapshot() -> None:
    first = snapshot_input()
    second = replace(first, symbol=Symbol("MSFT"))

    assert feature_content_digest(first) == feature_content_digest(second)
    assert feature_snapshot_key(first) != feature_snapshot_key(second)
