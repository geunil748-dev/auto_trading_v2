from datetime import UTC, datetime
from decimal import Decimal

from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshotInput,
    TradingDayHorizon,
)
from auto_trading_v2.domain.primitives import Symbol

AS_OF = datetime(2026, 7, 20, 15, tzinfo=UTC)


def provenance(
    key: str = "row-1",
    *,
    observed_at: datetime | None = None,
    available_at: datetime | None = None,
    digest_character: str = "a",
) -> FeatureProvenanceEntry:
    return FeatureProvenanceEntry(
        source_code="TEST_SOURCE",
        source_record_key=key,
        observed_at=AS_OF if observed_at is None else observed_at,
        available_at=AS_OF if available_at is None else available_at,
        content_digest=digest_character * 64,
        source_version="v1",
    )


def snapshot_input(
    *,
    feature_values: dict[str, object] | None = None,
    entries: tuple[FeatureProvenanceEntry, ...] | None = None,
    as_of: datetime = AS_OF,
    quality_status: FeatureQualityStatus = FeatureQualityStatus.READY,
    quality_reason_codes: tuple[str, ...] = (),
) -> FeatureSnapshotInput:
    return FeatureSnapshotInput(
        symbol=Symbol("AAPL"),
        feature_set_code="PRICE_TECHNICAL",
        feature_set_version="v1",
        horizon=TradingDayHorizon(3),
        as_of=as_of,
        feature_values=(
            {"close": Decimal("123.4500"), "volume": 100}
            if feature_values is None
            else feature_values
        ),
        provenance=(provenance(),) if entries is None else entries,
        quality_status=quality_status,
        quality_reason_codes=quality_reason_codes,
    )
