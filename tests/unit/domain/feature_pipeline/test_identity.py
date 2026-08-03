from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

import pytest

from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    PIPELINE_CODE,
    PIPELINE_VERSION,
    DailyFeaturePipelineIdentity,
    DailyFeaturePipelineValidationError,
    daily_feature_run_key,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.market_calendar import (
    CompletionGracePeriod,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
)
from auto_trading_v2.domain.primitives import SessionDate, UniverseSnapshotID


def identity() -> DailyFeaturePipelineIdentity:
    return DailyFeaturePipelineIdentity(
        UniverseSnapshotID(UUID(int=1)),
        "TWELVE_DATA_TIME_SERIES",
        ExchangeCalendarCode.US_EQUITY_CORE,
        ExchangeCalendarVersion.V2026_1,
        SessionDate(date(2026, 7, 31)),
        DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        TradingDayHorizon(1),
        30,
        datetime(2026, 8, 1, 9, tzinfo=timezone(timedelta(hours=9))),
        CompletionGracePeriod(timedelta(minutes=15)),
    )


def test_v1_identity_normalizes_as_of_and_has_exact_contract_constants() -> None:
    value = identity()

    assert value.as_of == datetime(2026, 8, 1, 0, tzinfo=UTC)
    assert value.pipeline_code == PIPELINE_CODE
    assert value.pipeline_version == PIPELINE_VERSION
    assert value.feature_set_code == FEATURE_SET_CODE
    assert value.feature_set_version == FEATURE_SET_VERSION
    assert daily_feature_run_key(value).startswith("daily-feature-run:v1:")
    assert len(daily_feature_run_key(value)) == 85


def test_same_instant_has_same_run_key_and_semantic_changes_change_key() -> None:
    source = identity()
    same = replace(source, as_of=datetime(2026, 8, 1, 0, tzinfo=UTC))

    assert daily_feature_run_key(source) == daily_feature_run_key(same)
    changes = (
        replace(source, provider_code="OTHER_PRIMARY"),
        replace(source, completed_session_date=None),
        replace(source, horizon=TradingDayHorizon(2)),
        replace(source, requested_session_count=31),
        replace(source, completion_grace=CompletionGracePeriod(timedelta(minutes=16))),
    )
    assert all(daily_feature_run_key(item) != daily_feature_run_key(source) for item in changes)


@pytest.mark.parametrize(
    ("field", "value", "category"),
    (
        ("provider_code", "contains secret / query", "PIPELINE_PROVIDER_CODE_INVALID"),
        ("requested_session_count", 20, "PIPELINE_REQUESTED_SESSIONS_INVALID"),
        ("pipeline_version", "v2", "PIPELINE_CONTRACT_VERSION_INVALID"),
        (
            "adjustment_basis",
            DailyMarketBarAdjustmentBasis.RAW,
            "PIPELINE_ADJUSTMENT_BASIS_INVALID",
        ),
    ),
)
def test_invalid_identity_is_rejected_with_safe_category(
    field: str,
    value: object,
    category: str,
) -> None:
    with pytest.raises(DailyFeaturePipelineValidationError) as caught:
        replace(identity(), **{field: value})

    assert caught.value.category == category
    assert "contains secret" not in str(caught.value)
