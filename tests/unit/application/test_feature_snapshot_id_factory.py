from uuid import UUID

from auto_trading_v2.adapters.identifiers import UuidFeatureSnapshotIDFactory
from auto_trading_v2.domain.primitives import FeatureSnapshotID, IdentifierFactory


def test_feature_snapshot_id_factory_reuses_typed_identifier_policy() -> None:
    expected = UUID("40000000-0000-0000-0000-000000000001")
    factory = UuidFeatureSnapshotIDFactory(IdentifierFactory(lambda: expected))

    assert factory.new() == FeatureSnapshotID(expected)
