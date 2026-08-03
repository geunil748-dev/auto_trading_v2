from dataclasses import replace
from decimal import Decimal, getcontext
from random import Random

import pytest

from auto_trading_v2.application.feature_building import (
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    PRICE_FEATURE_NAMES,
    PRICE_ONLY_FEATURE_SET_CODE,
    PRICE_ONLY_FEATURE_SET_VERSION,
    PRICE_ONLY_METADATA_NAMES,
    DailyPriceTechnicalFeatureBuilderV2,
    DailyTechnicalCalculationOutcome,
    DailyTechnicalFeatureBuilder,
    DailyTechnicalFeatureBuildError,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.feature_snapshots import (
    FeatureQualityStatus,
    FeatureSnapshotValidationError,
    TradingDayHorizon,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives import Currency, Symbol
from tests.unit.domain.daily_market_bars.helpers import BASE_TIME, stored_bar

_VOLUME_KEYS = {
    "volume_ratio_5_to_20",
    "latest_volume_to_avg20",
    "average_dollar_volume_20",
}


def _build_v2(bars: list[object]) -> object:
    return DailyPriceTechnicalFeatureBuilderV2().build(
        symbol=Symbol("AAPL"),
        source_code="UNIT_SOURCE",
        as_of=BASE_TIME.replace(year=2027),
        horizon=TradingDayHorizon(3),
        bars=bars,
    )


def _build_v1(bars: list[object]) -> object:
    return DailyTechnicalFeatureBuilder().build(
        symbol=Symbol("AAPL"),
        source_code="UNIT_SOURCE",
        as_of=BASE_TIME.replace(year=2027),
        horizon=TradingDayHorizon(3),
        bars=bars,
    )


@pytest.mark.parametrize("volume", [None, 0, 1000])
def test_v2_exact_payload_is_ready_and_volume_independent(volume: int | None) -> None:
    snapshot = _build_v2([stored_bar(index, volume=volume) for index in range(21)]).snapshot_input

    assert snapshot is not None
    assert (snapshot.feature_set_code, snapshot.feature_set_version) == (
        PRICE_ONLY_FEATURE_SET_CODE,
        PRICE_ONLY_FEATURE_SET_VERSION,
    )
    assert snapshot.quality_status is FeatureQualityStatus.READY
    assert snapshot.quality_reason_codes == ()
    assert set(snapshot.feature_values) == {*PRICE_FEATURE_NAMES, *PRICE_ONLY_METADATA_NAMES}
    assert not _VOLUME_KEYS.intersection(snapshot.feature_values)
    assert snapshot.feature_values["adjustment_basis"] == "SPLIT_ADJUSTED"
    assert snapshot.feature_values["completed_bar_count"] == 21


@pytest.mark.parametrize(
    ("volume", "v1_quality", "v1_reason"),
    [
        (None, FeatureQualityStatus.DEGRADED, "VOLUME_DATA_INCOMPLETE"),
        (0, FeatureQualityStatus.DEGRADED, "VOLUME_DATA_UNUSABLE"),
        (1000, FeatureQualityStatus.READY, None),
    ],
)
def test_v1_v2_price_parity_and_semantic_identity_are_distinct(
    volume: int | None,
    v1_quality: FeatureQualityStatus,
    v1_reason: str | None,
) -> None:
    bars = [stored_bar(index, volume=volume) for index in range(21)]
    v1 = _build_v1(bars).snapshot_input
    v2 = _build_v2(bars).snapshot_input

    assert v1 is not None and v2 is not None
    assert (v1.feature_set_code, v1.feature_set_version) == (FEATURE_SET_CODE, FEATURE_SET_VERSION)
    assert v1.quality_status is v1_quality
    assert v1.quality_reason_codes == (() if v1_reason is None else (v1_reason,))
    assert all(v1.feature_values[name] == v2.feature_values[name] for name in PRICE_FEATURE_NAMES)
    assert _VOLUME_KEYS.issubset(v1.feature_values)
    assert feature_snapshot_key(v1) != feature_snapshot_key(v2)
    assert feature_content_digest(v1) != feature_content_digest(v2)


def test_v2_insufficient_and_shuffled_order_are_deterministic() -> None:
    insufficient = _build_v2([stored_bar(index) for index in range(20)])
    bars = [stored_bar(index) for index in range(22)]
    shuffled = bars.copy()
    Random(7).shuffle(shuffled)

    assert insufficient.outcome is DailyTechnicalCalculationOutcome.DATA_INSUFFICIENT
    assert insufficient.snapshot_input is None
    assert _build_v2(bars).snapshot_input == _build_v2(shuffled).snapshot_input


@pytest.mark.parametrize(
    "mutation",
    [
        {"session_date": stored_bar(19).bar_input.session_date},
        {"symbol": Symbol("MSFT")},
        {"source_code": "OTHER_SOURCE"},
        {"adjustment_basis": DailyMarketBarAdjustmentBasis.RAW},
        {"available_at": BASE_TIME.replace(year=2028)},
    ],
)
def test_v2_rejects_noncanonical_bar_sets(mutation: dict[str, object]) -> None:
    bars = [stored_bar(index) for index in range(21)]
    bars[-1] = stored_bar(20, **mutation)

    with pytest.raises(DailyTechnicalFeatureBuildError):
        _build_v2(bars)


def test_v2_uses_local_decimal_context_and_rejects_float_boundary() -> None:
    before = getcontext().copy()
    snapshot = _build_v2([stored_bar(index) for index in range(21)]).snapshot_input

    assert snapshot is not None
    after = getcontext()
    assert (after.prec, after.rounding, after.traps, after.flags) == (
        before.prec,
        before.rounding,
        before.traps,
        before.flags,
    )
    with pytest.raises(FeatureSnapshotValidationError):
        replace(snapshot, feature_values={"last_close": 1.5})
    assert Decimal(snapshot.feature_values["last_close"]).is_finite()


def test_non_usd_bar_is_rejected_at_existing_value_boundary() -> None:
    with pytest.raises(DailyMarketBarValidationError):
        stored_bar(20, currency=Currency("KRW"))
