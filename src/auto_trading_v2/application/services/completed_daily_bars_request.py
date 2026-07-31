"""Create provider requests from completed-session calendar resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.completed_daily_bars import (
    CompletedDailyBarsRequestCreationOutcome,
    CompletedDailyBarsRequestCreationResult,
)
from auto_trading_v2.application.ports.daily_market_data import (
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.application.services.completed_session import (
    UsEquityCompletedSessionResolver,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.market_calendar import (
    CompletedSessionResolutionOutcome,
    CompletionGracePeriod,
)
from auto_trading_v2.domain.primitives import Symbol

_OUTCOME_MAP = {
    CompletedSessionResolutionOutcome.NO_COMPLETED_SESSION: (
        CompletedDailyBarsRequestCreationOutcome.NO_COMPLETED_SESSION
    ),
    CompletedSessionResolutionOutcome.CALENDAR_OUT_OF_COVERAGE: (
        CompletedDailyBarsRequestCreationOutcome.CALENDAR_OUT_OF_COVERAGE
    ),
    CompletedSessionResolutionOutcome.UNSUPPORTED_MIC: (
        CompletedDailyBarsRequestCreationOutcome.UNSUPPORTED_MIC
    ),
}


@dataclass(frozen=True, slots=True)
class CompletedDailyBarsRequestFactory:
    resolver: UsEquityCompletedSessionResolver

    def create(
        self,
        *,
        source_code: str,
        symbol: Symbol,
        mic_code: str,
        adjustment_basis: DailyMarketBarAdjustmentBasis,
        as_of: datetime,
        requested_session_count: int,
        completion_grace: CompletionGracePeriod,
    ) -> CompletedDailyBarsRequestCreationResult:
        resolution = self.resolver.resolve(
            mic_code=mic_code,
            as_of=as_of,
            completion_grace=completion_grace,
        )
        if resolution.outcome is not CompletedSessionResolutionOutcome.RESOLVED:
            outcome = _OUTCOME_MAP[resolution.outcome]
            return CompletedDailyBarsRequestCreationResult(
                outcome=outcome,
                calendar_code=resolution.calendar_code,
                calendar_version=resolution.calendar_version,
                safe_reason_code=outcome.value,
            )
        session = resolution.session
        assert session is not None
        return CompletedDailyBarsRequestCreationResult(
            outcome=CompletedDailyBarsRequestCreationOutcome.CREATED,
            calendar_code=resolution.calendar_code,
            calendar_version=resolution.calendar_version,
            request=FetchCompletedDailyBarsRequest(
                source_code=source_code,
                symbol=symbol,
                adjustment_basis=adjustment_basis,
                as_of=resolution.as_of,
                requested_session_count=requested_session_count,
                mic_code=session.mic_code,
                completed_through_session_date=session.session_date,
            ),
            completed_session=session,
            eligible_at=resolution.eligible_at,
        )
