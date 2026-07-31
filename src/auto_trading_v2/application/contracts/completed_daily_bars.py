"""Calendar-aware completed daily-bar request creation result."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.application.ports.daily_market_data import (
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
    MarketCalendarValidationError,
    MarketSession,
)

_SAFE_REASON = re.compile(r"^[A-Z0-9_]{1,96}$")


class CompletedDailyBarsRequestCreationOutcome(StrEnum):
    CREATED = "CREATED"
    NO_COMPLETED_SESSION = "NO_COMPLETED_SESSION"
    CALENDAR_OUT_OF_COVERAGE = "CALENDAR_OUT_OF_COVERAGE"
    UNSUPPORTED_MIC = "UNSUPPORTED_MIC"


@dataclass(frozen=True, slots=True)
class CompletedDailyBarsRequestCreationResult:
    outcome: CompletedDailyBarsRequestCreationOutcome
    calendar_code: ExchangeCalendarCode
    calendar_version: ExchangeCalendarVersion
    request: FetchCompletedDailyBarsRequest | None = None
    completed_session: MarketSession | None = None
    eligible_at: datetime | None = None
    safe_reason_code: str | None = None

    def __post_init__(self) -> None:
        created = self.outcome is CompletedDailyBarsRequestCreationOutcome.CREATED
        if created:
            if (
                self.request is None
                or self.completed_session is None
                or self.eligible_at is None
                or self.safe_reason_code is not None
            ):
                raise MarketCalendarValidationError("created request metadata가 올바르지 않습니다.")
        elif (
            self.request is not None
            or self.completed_session is not None
            or self.eligible_at is not None
            or self.safe_reason_code is None
        ):
            raise MarketCalendarValidationError("미생성 request 결과가 올바르지 않습니다.")
        if self.safe_reason_code is not None and not _SAFE_REASON.fullmatch(self.safe_reason_code):
            raise MarketCalendarValidationError("request reason code가 올바르지 않습니다.")
