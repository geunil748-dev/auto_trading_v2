"""Port for deterministic exchange-calendar schedules."""

from __future__ import annotations

from typing import Protocol

from auto_trading_v2.domain.market_calendar import (
    CalendarCoverage,
    MarketCalendarMetadata,
    MarketSession,
)
from auto_trading_v2.domain.primitives import SessionDate


class UsEquityMarketCalendar(Protocol):
    @property
    def metadata(self) -> MarketCalendarMetadata: ...

    @property
    def coverage(self) -> CalendarCoverage: ...

    @property
    def closure_dates(self) -> tuple[SessionDate, ...]: ...

    @property
    def early_close_dates(self) -> tuple[SessionDate, ...]: ...

    def sessions(self, mic_code: str) -> tuple[MarketSession, ...]: ...

    def sessions_between(
        self,
        mic_code: str,
        start_date: SessionDate,
        end_date: SessionDate,
    ) -> tuple[MarketSession, ...]: ...

    def session_on(
        self,
        mic_code: str,
        session_date: SessionDate,
    ) -> MarketSession | None: ...

    def latest_session_on_or_before(
        self,
        mic_code: str,
        session_date: SessionDate,
    ) -> MarketSession | None: ...

    def is_trading_session(self, mic_code: str, session_date: SessionDate) -> bool: ...
