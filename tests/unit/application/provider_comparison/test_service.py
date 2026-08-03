from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal, getcontext
from types import TracebackType

import pytest

from auto_trading_v2.application.contracts.daily_bar_comparison import (
    CompareDailyBarProvidersCommand,
    DailyBarProviderComparisonOutcome,
)
from auto_trading_v2.application.services import DailyBarProviderComparisonService
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from auto_trading_v2.domain.primitives import Symbol
from tests.unit.domain.daily_market_bars.helpers import stored_bar

NOW = datetime(2026, 7, 28, 12, tzinfo=UTC)


def bar(index: int, source: str, close: str) -> DailyMarketBar:
    existing = stored_bar(index)
    source_input = replace(
        existing.bar_input,
        source_code=source,
        source_record_key=f"{source}-{index}",
        close_price=Decimal(close),
        high_price=max(existing.bar_input.high_price, Decimal(close) + Decimal("1")),
        low_price=min(existing.bar_input.low_price, Decimal(close) - Decimal("1")),
    )
    return replace(
        existing,
        bar_key=daily_market_bar_key(source_input),
        content_digest=daily_market_bar_content_digest(source_input),
        bar_input=source_input,
    )


class Repository:
    def __init__(self, sources: dict[str, tuple[DailyMarketBar, ...]]) -> None:
        self.sources = sources
        self.calls: list[str] = []

    def list_latest_available(
        self,
        source_code,
        _symbol,
        _adjustment_basis,
        _as_of,
        limit,
    ):
        self.calls.append(source_code)
        return self.sources.get(source_code, ())[-limit:]


class UnitOfWork:
    def __init__(self, repository: Repository) -> None:
        self.daily_market_bars = repository

    def __enter__(self):
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        return None


class Factory:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return UnitOfWork(self.repository)


def command(minimum: int = 3) -> CompareDailyBarProvidersCommand:
    return CompareDailyBarProvidersCommand(
        primary_source_code="TWELVE_DATA_TIME_SERIES",
        validation_source_code="ALPACA_IEX_STOCK_BARS",
        symbol=Symbol("AAPL"),
        as_of=NOW,
        requested_session_count=30,
        minimum_overlap_sessions=minimum,
    )


def test_comparable_metrics_are_decimal_read_only_and_context_local() -> None:
    primary = tuple(
        bar(index, "TWELVE_DATA_TIME_SERIES", close)
        for index, close in enumerate(("100", "101", "102"))
    )
    validation = tuple(
        bar(index, "ALPACA_IEX_STOCK_BARS", close)
        for index, close in enumerate(("100", "99", "100"))
    )
    repository = Repository(
        {
            "TWELVE_DATA_TIME_SERIES": primary,
            "ALPACA_IEX_STOCK_BARS": validation,
        }
    )
    factory = Factory(repository)
    original_precision = getcontext().prec
    original_rounding = getcontext().rounding
    getcontext().rounding = ROUND_DOWN
    try:
        report = DailyBarProviderComparisonService(factory).compare(command())
        assert getcontext().prec == original_precision
        assert getcontext().rounding is ROUND_DOWN
    finally:
        getcontext().rounding = original_rounding

    assert report.outcome is DailyBarProviderComparisonOutcome.COMPARABLE
    assert report.overlap_count == 3
    assert report.primary_only_session_count == 0
    assert report.validation_only_session_count == 0
    assert report.median_absolute_close_relative_difference == Decimal(
        "0.01960784313725490196078431372549019608"
    )
    assert report.maximum_absolute_close_relative_difference == Decimal(
        "0.01980198019801980198019801980198019802"
    )
    assert report.return_direction_agreement_count == 1
    assert report.return_direction_observation_count == 2
    assert report.return_direction_agreement_rate == Decimal("0.5")
    assert factory.calls == 2
    assert repository.calls == ["TWELVE_DATA_TIME_SERIES", "ALPACA_IEX_STOCK_BARS"]


@pytest.mark.parametrize(
    ("primary", "validation", "minimum", "outcome"),
    (
        ((), (), 1, DailyBarProviderComparisonOutcome.PRIMARY_DATA_MISSING),
        (
            (bar(0, "TWELVE_DATA_TIME_SERIES", "100"),),
            (),
            1,
            DailyBarProviderComparisonOutcome.VALIDATION_DATA_MISSING,
        ),
        (
            (bar(0, "TWELVE_DATA_TIME_SERIES", "100"),),
            (bar(1, "ALPACA_IEX_STOCK_BARS", "101"),),
            1,
            DailyBarProviderComparisonOutcome.INSUFFICIENT_OVERLAP,
        ),
    ),
)
def test_non_comparable_outcomes_have_no_derived_metrics(
    primary: tuple[DailyMarketBar, ...],
    validation: tuple[DailyMarketBar, ...],
    minimum: int,
    outcome: DailyBarProviderComparisonOutcome,
) -> None:
    repository = Repository(
        {
            "TWELVE_DATA_TIME_SERIES": primary,
            "ALPACA_IEX_STOCK_BARS": validation,
        }
    )

    report = DailyBarProviderComparisonService(Factory(repository)).compare(command(minimum))

    assert report.outcome is outcome
    assert report.median_absolute_close_relative_difference is None
    assert report.maximum_absolute_close_relative_difference is None
    assert report.return_direction_observation_count == 0


def test_missing_session_counts_do_not_mix_provider_rows() -> None:
    primary = (
        bar(0, "TWELVE_DATA_TIME_SERIES", "100"),
        bar(1, "TWELVE_DATA_TIME_SERIES", "101"),
        bar(2, "TWELVE_DATA_TIME_SERIES", "102"),
    )
    validation = (
        bar(1, "ALPACA_IEX_STOCK_BARS", "101"),
        bar(2, "ALPACA_IEX_STOCK_BARS", "102"),
        bar(3, "ALPACA_IEX_STOCK_BARS", "103"),
    )
    repository = Repository(
        {
            "TWELVE_DATA_TIME_SERIES": primary,
            "ALPACA_IEX_STOCK_BARS": validation,
        }
    )

    report = DailyBarProviderComparisonService(Factory(repository)).compare(command(2))

    assert report.outcome is DailyBarProviderComparisonOutcome.COMPARABLE
    assert report.primary_bar_count == 3
    assert report.validation_bar_count == 3
    assert report.overlap_count == 2
    assert report.primary_only_session_count == 1
    assert report.validation_only_session_count == 1


def test_even_median_zero_return_and_input_order_are_deterministic() -> None:
    primary = (
        bar(0, "TWELVE_DATA_TIME_SERIES", "100"),
        bar(1, "TWELVE_DATA_TIME_SERIES", "100"),
    )
    validation = (
        bar(0, "ALPACA_IEX_STOCK_BARS", "99"),
        bar(1, "ALPACA_IEX_STOCK_BARS", "97"),
    )
    forward = Repository(
        {
            "TWELVE_DATA_TIME_SERIES": primary,
            "ALPACA_IEX_STOCK_BARS": validation,
        }
    )
    reverse = Repository(
        {
            "TWELVE_DATA_TIME_SERIES": tuple(reversed(primary)),
            "ALPACA_IEX_STOCK_BARS": tuple(reversed(validation)),
        }
    )

    forward_report = DailyBarProviderComparisonService(Factory(forward)).compare(command(2))
    reverse_report = DailyBarProviderComparisonService(Factory(reverse)).compare(command(2))

    assert forward_report == reverse_report
    assert forward_report.median_absolute_close_relative_difference == Decimal("0.02")
    assert forward_report.return_direction_agreement_count == 0
    assert forward_report.return_direction_observation_count == 1

    zero_validation = Repository(
        {
            "TWELVE_DATA_TIME_SERIES": primary,
            "ALPACA_IEX_STOCK_BARS": (
                bar(0, "ALPACA_IEX_STOCK_BARS", "99"),
                bar(1, "ALPACA_IEX_STOCK_BARS", "99"),
            ),
        }
    )
    zero_report = DailyBarProviderComparisonService(Factory(zero_validation)).compare(command(2))
    assert zero_report.return_direction_agreement_count == 1
    assert zero_report.return_direction_agreement_rate == Decimal(1)
