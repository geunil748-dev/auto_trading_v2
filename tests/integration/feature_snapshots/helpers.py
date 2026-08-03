from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidFeatureSnapshotIDFactory
from auto_trading_v2.application.contracts.feature_snapshots import (
    CreateFeatureSnapshotCommand,
    NewFeatureSnapshot,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services import FeatureSnapshotCreationService
from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshot,
    TradingDayHorizon,
    feature_content_digest,
    feature_snapshot_key,
    plain_json,
)
from auto_trading_v2.domain.primitives import (
    FeatureSnapshotID,
    IdentifierFactory,
    Symbol,
)

BASE_AS_OF = datetime(2026, 7, 21, 6, tzinfo=UTC)


def command(
    case: int,
    feature_values: Mapping[str, object] | None = None,
) -> CreateFeatureSnapshotCommand:
    as_of = BASE_AS_OF + timedelta(minutes=case)
    values = (
        {
            "close": Decimal("123.4500"),
            "nested": {"목록": ["값", Decimal("0.0100")]},
            "signal": True,
        }
        if feature_values is None
        else feature_values
    )
    return CreateFeatureSnapshotCommand(
        symbol=Symbol("AAPL"),
        feature_set_code="PRICE_TECHNICAL",
        feature_set_version="v1",
        horizon=TradingDayHorizon(3),
        as_of=as_of,
        feature_values=values,
        provenance=(
            FeatureProvenanceEntry(
                source_code="SOURCE_B",
                source_record_key=f"row-b-{case}",
                observed_at=as_of - timedelta(minutes=2),
                available_at=as_of,
                content_digest="b" * 64,
                source_version="v2",
            ),
            FeatureProvenanceEntry(
                source_code="SOURCE_A",
                source_record_key=f"row-a-{case}",
                observed_at=as_of - timedelta(minutes=3),
                available_at=as_of - timedelta(minutes=1),
                content_digest="a" * 64,
                source_version="v1",
            ),
        ),
        quality_status=FeatureQualityStatus.READY,
    )


def new_snapshot(
    case: int,
    *,
    identifier: int | None = None,
    feature_values: Mapping[str, object] | None = None,
) -> NewFeatureSnapshot:
    source = command(case, feature_values).snapshot_input
    return NewFeatureSnapshot(
        feature_snapshot_id=FeatureSnapshotID(UUID(int=identifier or case)),
        snapshot_key=feature_snapshot_key(source),
        content_digest=feature_content_digest(source),
        snapshot_input=source,
        generated_at=source.as_of + timedelta(seconds=1),
    )


def creation_service(
    unit_of_work_factory: UnitOfWorkFactory,
    case: int,
) -> FeatureSnapshotCreationService:
    generated_at = command(case).as_of + timedelta(seconds=1)
    identifier_factory = IdentifierFactory(lambda: UUID(int=case))
    return FeatureSnapshotCreationService(
        unit_of_work_factory,
        FixedClock(generated_at),
        UuidFeatureSnapshotIDFactory(identifier_factory),
    )


def assert_same_snapshot(actual: FeatureSnapshot, expected: FeatureSnapshot) -> None:
    assert actual.feature_snapshot_id == expected.feature_snapshot_id
    assert actual.snapshot_key == expected.snapshot_key
    assert actual.content_digest == expected.content_digest
    actual_input = actual.snapshot_input
    expected_input = expected.snapshot_input
    assert actual_input.symbol == expected_input.symbol
    assert actual_input.feature_set_code == expected_input.feature_set_code
    assert actual_input.feature_set_version == expected_input.feature_set_version
    assert actual_input.horizon == expected_input.horizon
    assert actual_input.as_of == expected_input.as_of
    assert actual.generated_at == expected.generated_at
    assert actual_input.latest_input_available_at == expected_input.latest_input_available_at
    assert actual_input.quality_status == expected_input.quality_status
    assert actual_input.quality_reason_codes == expected_input.quality_reason_codes
    assert plain_json(actual_input.feature_values) == plain_json(expected_input.feature_values)
    assert actual_input.provenance == expected_input.provenance
    assert actual.recorded_at == expected.recorded_at
    assert actual.recorded_at.utcoffset() == timedelta(0)
