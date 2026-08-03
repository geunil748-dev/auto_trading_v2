"""Read-only session-aligned daily-bar comparison without provider blending."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from auto_trading_v2.application.contracts.daily_bar_comparison import (
    CompareDailyBarProvidersCommand,
    DailyBarProviderComparisonOutcome,
    DailyBarProviderComparisonReport,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
)

_DECIMAL_CONTEXT = Context(prec=38, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class DailyBarProviderComparisonService:
    unit_of_work_factory: UnitOfWorkFactory

    def compare(
        self,
        command: CompareDailyBarProvidersCommand,
    ) -> DailyBarProviderComparisonReport:
        primary = self._read(command, command.primary_source_code)
        validation = self._read(command, command.validation_source_code)
        primary_by_session = {bar.bar_input.session_date.value: bar for bar in primary}
        validation_by_session = {bar.bar_input.session_date.value: bar for bar in validation}
        common = sorted(primary_by_session.keys() & validation_by_session.keys())
        outcome = _outcome(
            len(primary),
            len(validation),
            len(common),
            command.minimum_overlap_sessions,
        )
        close_metrics: tuple[Decimal | None, Decimal | None] = (None, None)
        direction_metrics: tuple[int, int, Decimal | None] = (0, 0, None)
        if outcome is DailyBarProviderComparisonOutcome.COMPARABLE:
            with localcontext(_DECIMAL_CONTEXT):
                close_metrics = _close_metrics(
                    common,
                    primary_by_session,
                    validation_by_session,
                )
                direction_metrics = _direction_metrics(
                    common,
                    primary_by_session,
                    validation_by_session,
                )
        return DailyBarProviderComparisonReport(
            outcome=outcome,
            primary_source_code=command.primary_source_code,
            validation_source_code=command.validation_source_code,
            symbol=command.symbol,
            as_of=command.as_of,
            primary_bar_count=len(primary),
            validation_bar_count=len(validation),
            overlap_count=len(common),
            primary_only_session_count=len(primary_by_session.keys() - set(common)),
            validation_only_session_count=len(validation_by_session.keys() - set(common)),
            median_absolute_close_relative_difference=close_metrics[0],
            maximum_absolute_close_relative_difference=close_metrics[1],
            return_direction_agreement_count=direction_metrics[0],
            return_direction_observation_count=direction_metrics[1],
            return_direction_agreement_rate=direction_metrics[2],
        )

    def _read(
        self,
        command: CompareDailyBarProvidersCommand,
        source_code: str,
    ) -> tuple[DailyMarketBar, ...]:
        with self.unit_of_work_factory() as unit_of_work:
            return unit_of_work.daily_market_bars.list_latest_available(
                source_code,
                command.symbol,
                DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
                command.as_of,
                command.requested_session_count,
            )


def _outcome(
    primary_count: int,
    validation_count: int,
    overlap_count: int,
    minimum_overlap_sessions: int,
) -> DailyBarProviderComparisonOutcome:
    if primary_count == 0:
        return DailyBarProviderComparisonOutcome.PRIMARY_DATA_MISSING
    if validation_count == 0:
        return DailyBarProviderComparisonOutcome.VALIDATION_DATA_MISSING
    if overlap_count < minimum_overlap_sessions:
        return DailyBarProviderComparisonOutcome.INSUFFICIENT_OVERLAP
    return DailyBarProviderComparisonOutcome.COMPARABLE


def _close_metrics(
    sessions: Sequence[date],
    primary: Mapping[date, DailyMarketBar],
    validation: Mapping[date, DailyMarketBar],
) -> tuple[Decimal, Decimal]:
    differences = sorted(
        abs(
            validation[session].bar_input.close_price / primary[session].bar_input.close_price
            - Decimal(1)
        )
        for session in sessions
    )
    middle = len(differences) // 2
    median = (
        differences[middle]
        if len(differences) % 2
        else (differences[middle - 1] + differences[middle]) / Decimal(2)
    )
    return median, differences[-1]


def _direction_metrics(
    sessions: Sequence[date],
    primary: Mapping[date, DailyMarketBar],
    validation: Mapping[date, DailyMarketBar],
) -> tuple[int, int, Decimal | None]:
    observations = max(0, len(sessions) - 1)
    if observations == 0:
        return 0, 0, None
    agreements = 0
    for previous, current in zip(sessions, sessions[1:], strict=False):
        primary_direction = _sign(
            primary[current].bar_input.close_price - primary[previous].bar_input.close_price
        )
        validation_direction = _sign(
            validation[current].bar_input.close_price - validation[previous].bar_input.close_price
        )
        agreements += int(primary_direction == validation_direction)
    return agreements, observations, Decimal(agreements) / Decimal(observations)


def _sign(value: Decimal) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0
