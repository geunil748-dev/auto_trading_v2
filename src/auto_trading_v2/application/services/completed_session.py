"""Resolve the latest eligible completed US equity core session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from auto_trading_v2.application.ports.market_calendar import UsEquityMarketCalendar
from auto_trading_v2.domain.market_calendar import (
    CompletedSessionResolution,
    CompletedSessionResolutionOutcome,
    CompletionGracePeriod,
    MarketCalendarValidationError,
    calendar_family_for_mic,
    normalize_supported_mic,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class UsEquityCompletedSessionResolver:
    calendar: UsEquityMarketCalendar

    def resolve(
        self,
        *,
        mic_code: str,
        as_of: datetime,
        completion_grace: CompletionGracePeriod,
    ) -> CompletedSessionResolution:
        if not isinstance(completion_grace, CompletionGracePeriod):
            raise MarketCalendarValidationError("completion_grace 타입이 올바르지 않습니다.")
        try:
            normalized_as_of = normalize_utc(as_of)
        except Exception:
            raise MarketCalendarValidationError("as_of에는 시간대 정보가 필요합니다.") from None
        if calendar_family_for_mic(mic_code) is None:
            return self._unresolved(
                CompletedSessionResolutionOutcome.UNSUPPORTED_MIC,
                normalized_as_of,
            )
        normalized_mic = normalize_supported_mic(mic_code)
        exchange_date = normalized_as_of.astimezone(_NEW_YORK).date()
        if not self.calendar.coverage.contains(exchange_date):
            return self._unresolved(
                CompletedSessionResolutionOutcome.CALENDAR_OUT_OF_COVERAGE,
                normalized_as_of,
            )
        sessions = self.calendar.sessions(normalized_mic)
        for index in range(len(sessions) - 1, -1, -1):
            session = sessions[index]
            eligible_at = session.close_at + completion_grace.value
            if normalized_as_of >= eligible_at:
                previous = sessions[index - 1].session_date if index else None
                return CompletedSessionResolution(
                    outcome=CompletedSessionResolutionOutcome.RESOLVED,
                    as_of=normalized_as_of,
                    calendar_code=self.calendar.metadata.calendar_code,
                    calendar_version=self.calendar.metadata.calendar_version,
                    session=session,
                    eligible_at=eligible_at,
                    previous_session_date=previous,
                )
        return self._unresolved(
            CompletedSessionResolutionOutcome.NO_COMPLETED_SESSION,
            normalized_as_of,
        )

    def _unresolved(
        self,
        outcome: CompletedSessionResolutionOutcome,
        as_of: datetime,
    ) -> CompletedSessionResolution:
        return CompletedSessionResolution(
            outcome=outcome,
            as_of=as_of,
            calendar_code=self.calendar.metadata.calendar_code,
            calendar_version=self.calendar.metadata.calendar_version,
        )
