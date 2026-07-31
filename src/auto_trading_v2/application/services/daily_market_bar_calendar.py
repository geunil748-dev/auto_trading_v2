"""Validate provider daily bars against the selected official calendar."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from auto_trading_v2.application.ports.market_calendar import UsEquityMarketCalendar
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarInput
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
    ProviderBarCalendarErrorCategory,
    calendar_family_for_mic,
    normalize_supported_mic,
)
from auto_trading_v2.domain.primitives import SessionDate


@dataclass(frozen=True, slots=True)
class DailyMarketBarCalendarValidator:
    calendar: UsEquityMarketCalendar

    def validate(
        self,
        *,
        mic_code: str,
        calendar_code: ExchangeCalendarCode,
        calendar_version: ExchangeCalendarVersion,
        completed_through_session_date: SessionDate,
        observations: Iterable[DailyMarketBarInput],
    ) -> tuple[DailyMarketBarInput, ...]:
        if calendar_family_for_mic(mic_code) is None:
            self._raise(ProviderBarCalendarErrorCategory.UNSUPPORTED_MIC)
        normalized_mic = normalize_supported_mic(mic_code)
        if (
            calendar_code is not self.calendar.metadata.calendar_code
            or calendar_version is not self.calendar.metadata.calendar_version
            or not isinstance(completed_through_session_date, SessionDate)
            or not self.calendar.coverage.contains(completed_through_session_date.value)
        ):
            self._raise(ProviderBarCalendarErrorCategory.OUT_OF_CALENDAR_COVERAGE)
        values = tuple(observations)
        first_identity: tuple[object, str] | None = None
        previous_date: date | None = None
        seen_dates: set[date] = set()
        for observation in values:
            if not isinstance(observation, DailyMarketBarInput):
                self._raise(ProviderBarCalendarErrorCategory.SEQUENCE_INCONSISTENT)
            session_date = observation.session_date
            if not self.calendar.coverage.contains(session_date.value):
                self._raise(ProviderBarCalendarErrorCategory.OUT_OF_CALENDAR_COVERAGE)
            if session_date.value > completed_through_session_date.value:
                self._raise(ProviderBarCalendarErrorCategory.AFTER_COMPLETED_CUTOFF)
            if session_date.value in seen_dates:
                self._raise(ProviderBarCalendarErrorCategory.DUPLICATE_SESSION)
            if not self.calendar.is_trading_session(normalized_mic, session_date):
                self._raise(ProviderBarCalendarErrorCategory.ON_NON_TRADING_DAY)
            identity = (observation.symbol, observation.source_code)
            if first_identity is None:
                first_identity = identity
            elif identity != first_identity:
                self._raise(ProviderBarCalendarErrorCategory.SEQUENCE_INCONSISTENT)
            if previous_date is not None and session_date.value < previous_date:
                self._raise(ProviderBarCalendarErrorCategory.SEQUENCE_INCONSISTENT)
            previous_date = session_date.value
            seen_dates.add(session_date.value)
        return values

    @staticmethod
    def _raise(category: ProviderBarCalendarErrorCategory) -> None:
        raise MarketCalendarValidationError(
            "provider daily bar calendar validation failed",
            category=category.value,
        )
