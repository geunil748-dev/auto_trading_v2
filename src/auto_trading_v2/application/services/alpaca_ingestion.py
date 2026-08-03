"""Revision-safe Alpaca IEX DailyMarketBar validation ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from auto_trading_v2.adapters.market_data.alpaca import (
    ALPACA_SOURCE_CODE,
    ALPACA_SOURCE_FEED,
    AlpacaErrorCategory,
    AlpacaProviderError,
)
from auto_trading_v2.application.contracts.alpaca_ingestion import (
    AlpacaDailyMarketBarIngestionCommand,
    AlpacaIngestionOutcome,
    AlpacaIngestionResult,
    AlpacaIngestionSummary,
)
from auto_trading_v2.application.contracts.daily_market_bars import (
    CreateDailyMarketBarCommand,
    DailyMarketBarCreationOutcome,
)
from auto_trading_v2.application.daily_market_bar_errors import (
    DailyMarketBarConflictError,
)
from auto_trading_v2.application.ports.daily_market_data import DailyMarketDataProvider
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_market_bar import (
    DailyMarketBarCreationService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBar, DailyMarketBarInput
from auto_trading_v2.domain.market_calendar import MarketCalendarValidationError
from auto_trading_v2.ports.clock import Clock

from .daily_market_bar_calendar import DailyMarketBarCalendarValidator


@dataclass(frozen=True, slots=True)
class AlpacaDailyMarketBarIngestionService:
    provider: DailyMarketDataProvider
    unit_of_work_factory: UnitOfWorkFactory
    creation_service: DailyMarketBarCreationService
    clock: Clock
    calendar_validator: DailyMarketBarCalendarValidator

    def ingest(self, command: AlpacaDailyMarketBarIngestionCommand) -> AlpacaIngestionResult:
        from auto_trading_v2.application.ports.daily_market_data import (
            FetchCompletedDailyBarsRequest,
        )

        request = FetchCompletedDailyBarsRequest(
            source_code=ALPACA_SOURCE_CODE,
            symbol=command.symbol,
            adjustment_basis=command.adjustment_basis,
            as_of=self.clock.now_utc(),
            requested_session_count=command.requested_session_count,
            mic_code=command.mic_code,
            completed_through_session_date=command.completed_through_session_date,
        )
        try:
            observations = self.provider.fetch_completed_daily_bars(request)
        except AlpacaProviderError as error:
            return self._provider_failure(command, error.category)
        try:
            observations = self.calendar_validator.validate(
                mic_code=command.mic_code,
                calendar_code=self.calendar_validator.calendar.metadata.calendar_code,
                calendar_version=self.calendar_validator.calendar.metadata.calendar_version,
                completed_through_session_date=command.completed_through_session_date,
                observations=observations,
            )
        except MarketCalendarValidationError as error:
            return self._result(
                command,
                AlpacaIngestionOutcome.PROVIDER_ERROR,
                len(observations),
                0,
                0,
                (),
                error.category,
            )
        if not observations:
            return self._result(command, AlpacaIngestionOutcome.NO_DATA, 0, 0, 0, ())
        stored: list[DailyMarketBar] = []
        created_count = existing_count = 0
        for observation in observations:
            if not self._matches(command, observation):
                return self._result(
                    command,
                    AlpacaIngestionOutcome.PROVIDER_ERROR,
                    len(observations),
                    created_count,
                    existing_count,
                    tuple(stored),
                    AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID.value,
                )
            existing = self._existing(observation)
            if existing is not None:
                stored.append(existing)
                existing_count += 1
                continue
            try:
                created = self.creation_service.create(_creation_command(observation))
            except DailyMarketBarConflictError:
                raced = self._existing(observation)
                if raced is None:
                    return self._result(
                        command,
                        AlpacaIngestionOutcome.INGESTION_CONFLICT,
                        len(observations),
                        created_count,
                        existing_count,
                        tuple(stored),
                        AlpacaErrorCategory.INGESTION_CONFLICT.value,
                    )
                stored.append(raced)
                existing_count += 1
                continue
            stored.append(created.bar)
            if created.outcome is DailyMarketBarCreationOutcome.CREATED:
                created_count += 1
            else:
                existing_count += 1
        outcome = (
            AlpacaIngestionOutcome.COMPLETED_WITH_EXISTING
            if existing_count
            else AlpacaIngestionOutcome.COMPLETED
        )
        return self._result(
            command,
            outcome,
            len(observations),
            created_count,
            existing_count,
            tuple(stored),
        )

    def _existing(self, source: DailyMarketBarInput) -> DailyMarketBar | None:
        with self.unit_of_work_factory() as unit_of_work:
            return unit_of_work.daily_market_bars.get_by_source_identity(
                source.source_code,
                source.source_record_key,
                source.source_version,
            )

    @staticmethod
    def _matches(
        command: AlpacaDailyMarketBarIngestionCommand,
        source: DailyMarketBarInput,
    ) -> bool:
        return (
            source.source_code == ALPACA_SOURCE_CODE
            and source.symbol == command.symbol
            and source.adjustment_basis is command.adjustment_basis
            and source.session_date.value <= command.completed_through_session_date.value
        )

    def _provider_failure(
        self,
        command: AlpacaDailyMarketBarIngestionCommand,
        category: AlpacaErrorCategory,
    ) -> AlpacaIngestionResult:
        outcomes = {
            AlpacaErrorCategory.PROVIDER_DISABLED: AlpacaIngestionOutcome.PROVIDER_DISABLED,
            AlpacaErrorCategory.CONFIGURATION_MISSING: (
                AlpacaIngestionOutcome.PROVIDER_CONFIGURATION_MISSING
            ),
        }
        return self._result(
            command,
            outcomes.get(category, AlpacaIngestionOutcome.PROVIDER_ERROR),
            0,
            0,
            0,
            (),
            category.value,
        )

    @staticmethod
    def _result(
        command: AlpacaDailyMarketBarIngestionCommand,
        outcome: AlpacaIngestionOutcome,
        fetched_count: int,
        created_count: int,
        existing_count: int,
        bars: tuple[DailyMarketBar, ...],
        safe_error_category: str | None = None,
    ) -> AlpacaIngestionResult:
        sessions = tuple(bar.bar_input.session_date for bar in bars)
        return AlpacaIngestionResult(
            outcome,
            AlpacaIngestionSummary(
                provider_code=ALPACA_SOURCE_CODE,
                source_feed=ALPACA_SOURCE_FEED,
                symbol=command.symbol,
                mic_code=command.mic_code,
                adjustment_basis=command.adjustment_basis,
                completed_through_session_date=command.completed_through_session_date,
                fetched_count=fetched_count,
                created_count=created_count,
                existing_count=existing_count,
                oldest_session_date=min(sessions, key=lambda value: value.value)
                if sessions
                else None,
                newest_session_date=max(sessions, key=lambda value: value.value)
                if sessions
                else None,
                safe_error_category=safe_error_category,
            ),
            bars,
        )


def _creation_command(source: DailyMarketBarInput) -> CreateDailyMarketBarCommand:
    return CreateDailyMarketBarCommand(
        source_code=source.source_code,
        source_record_key=source.source_record_key,
        source_version=source.source_version,
        symbol=source.symbol,
        currency=source.currency,
        adjustment_basis=source.adjustment_basis,
        session_date=source.session_date,
        observed_at=source.observed_at,
        available_at=source.available_at,
        open_price=source.open_price,
        high_price=source.high_price,
        low_price=source.low_price,
        close_price=source.close_price,
        volume=source.volume,
    )
