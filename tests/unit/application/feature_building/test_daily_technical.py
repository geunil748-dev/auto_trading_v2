from dataclasses import replace
from decimal import ROUND_HALF_EVEN, Context, Decimal, getcontext, localcontext
from random import Random

import pytest

from auto_trading_v2.application.feature_building import (
    INSUFFICIENT_REASON,
    DailyTechnicalCalculationOutcome,
    DailyTechnicalFeatureBuilder,
    DailyTechnicalFeatureBuildError,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_snapshots import (
    FeatureQualityStatus,
    TradingDayHorizon,
)
from auto_trading_v2.domain.primitives import Symbol
from tests.unit.domain.daily_market_bars.helpers import BASE_TIME, stored_bar


def _build(bars: list[object]) -> object:
    return DailyTechnicalFeatureBuilder().build(
        symbol=Symbol("AAPL"),
        source_code="UNIT_SOURCE",
        as_of=BASE_TIME.replace(year=2027),
        horizon=TradingDayHorizon(3),
        bars=bars,
    )


def _decimal(value: object) -> Decimal:
    assert isinstance(value, str)
    return Decimal(value)


def test_exactly_21_complete_bars_build_all_17_v1_features() -> None:
    bars = [stored_bar(index) for index in range(21)]
    result = _build(bars)

    assert result.outcome is DailyTechnicalCalculationOutcome.SNAPSHOT_READY
    snapshot = result.snapshot_input
    assert snapshot is not None
    values = snapshot.feature_values
    with localcontext(Context(prec=38, rounding=ROUND_HALF_EVEN)):
        close = tuple(Decimal(100 + index) for index in range(21))
        returns = tuple(close[index] / close[index - 1] - 1 for index in range(1, 21))
        mean = sum(returns, Decimal(0)) / Decimal(20)
        expected = {
            "last_close": close[20],
            "one_day_return": close[20] / close[19] - 1,
            "five_day_return": close[20] / close[15] - 1,
            "twenty_day_return": close[20] / close[0] - 1,
            "latest_gap_return": (close[20] - Decimal("0.5")) / close[19] - 1,
            "latest_intraday_return": close[20] / (close[20] - Decimal("0.5")) - 1,
            "latest_range_rate": Decimal(4) / close[19],
            "close_vs_sma5": close[20] / (sum(close[16:21]) / Decimal(5)) - 1,
            "close_vs_sma10": close[20] / (sum(close[11:21]) / Decimal(10)) - 1,
            "close_vs_sma20": close[20] / (sum(close[1:21]) / Decimal(20)) - 1,
            "realized_volatility_20d": (
                sum(((value - mean) ** 2 for value in returns), Decimal(0)) / Decimal(20)
            ).sqrt(),
            "atr14_rate": Decimal(4) / close[20],
            "distance_from_prior_20d_high": close[20] / Decimal(121) - 1,
            "distance_from_prior_20d_low": close[20] / Decimal(98) - 1,
            "volume_ratio_5_to_20": Decimal(1180) / Decimal(1105),
            "latest_volume_to_avg20": Decimal(1200) / Decimal(1105),
            "average_dollar_volume_20": sum(
                close[index] * Decimal(1000 + index * 10) for index in range(1, 21)
            )
            / Decimal(20),
        }
    assert set(expected) == {
        key for key in values if key not in {"adjustment_basis", "completed_bar_count"}
    }
    for name, expected_value in expected.items():
        assert _decimal(values[name]) == expected_value
    assert values["adjustment_basis"] == "SPLIT_ADJUSTED"
    assert values["completed_bar_count"] == 21
    assert snapshot.quality_status is FeatureQualityStatus.READY
    assert len(snapshot.provenance) == 21
    assert {entry.content_digest for entry in snapshot.provenance} == {
        bar.content_digest for bar in bars
    }


def test_20_bars_returns_normal_data_insufficient_without_snapshot() -> None:
    result = _build([stored_bar(index) for index in range(20)])

    assert result.outcome is DailyTechnicalCalculationOutcome.DATA_INSUFFICIENT
    assert result.snapshot_input is None
    assert result.reason_codes == (INSUFFICIENT_REASON,)


def test_22_bars_use_latest_21_and_shuffled_input_is_deterministic() -> None:
    bars = [stored_bar(index) for index in range(22)]
    shuffled = bars.copy()
    Random(7).shuffle(shuffled)

    ordered_result = _build(bars)
    shuffled_result = _build(shuffled)

    assert ordered_result.snapshot_input == shuffled_result.snapshot_input
    snapshot = ordered_result.snapshot_input
    assert snapshot is not None
    with localcontext(Context(prec=38, rounding=ROUND_HALF_EVEN)):
        expected_return = Decimal(121) / Decimal(101) - 1
    assert _decimal(snapshot.feature_values["twenty_day_return"]) == expected_return
    assert bars[0].content_digest not in {entry.content_digest for entry in snapshot.provenance}


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
def test_mixed_duplicate_raw_and_future_inputs_are_rejected(
    mutation: dict[str, object],
) -> None:
    bars = [stored_bar(index) for index in range(21)]
    changed_input = replace(bars[20].bar_input, **mutation)
    bars[20] = stored_bar(
        20, **{name: getattr(changed_input, name) for name in changed_input.__dataclass_fields__}
    )

    with pytest.raises(DailyTechnicalFeatureBuildError):
        _build(bars)


def test_volume_none_degrades_and_nulls_all_volume_features() -> None:
    bars = [stored_bar(index) for index in range(21)]
    bars[10] = stored_bar(10, volume=None)

    result = _build(bars)
    snapshot = result.snapshot_input
    assert snapshot is not None
    assert snapshot.quality_status is FeatureQualityStatus.DEGRADED
    assert snapshot.quality_reason_codes == ("VOLUME_DATA_INCOMPLETE",)
    for name in (
        "volume_ratio_5_to_20",
        "latest_volume_to_avg20",
        "average_dollar_volume_20",
    ):
        assert snapshot.feature_values[name] is None


def test_zero_twenty_day_average_volume_degrades_as_unusable() -> None:
    bars = [stored_bar(index, volume=0) for index in range(21)]

    snapshot = _build(bars).snapshot_input

    assert snapshot is not None
    assert snapshot.quality_status is FeatureQualityStatus.DEGRADED
    assert snapshot.quality_reason_codes == ("VOLUME_DATA_UNUSABLE",)


def test_builder_does_not_change_process_global_decimal_context() -> None:
    before = getcontext().copy()

    _build([stored_bar(index) for index in range(21)])

    after = getcontext()
    assert after.prec == before.prec
    assert after.rounding == before.rounding
    assert after.traps == before.traps
    assert after.flags == before.flags
