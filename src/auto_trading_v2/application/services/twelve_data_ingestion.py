"""Revision-safe Twelve Data DailyMarketBar ingestion orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)
from auto_trading_v2.application.contracts.daily_market_bars import (
    CreateDailyMarketBarCommand,
    DailyMarketBarCreationOutcome,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionCommand,
    TwelveDataIngestionOutcome,
    TwelveDataIngestionResult,
    TwelveDataIngestionSummary,
)
from auto_trading_v2.application.daily_market_bar_errors import (
    DailyMarketBarConflictError,
)
from auto_trading_v2.application.ports.daily_market_data import (
    DailyMarketDataProvider,
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.daily_market_bar import (
    DailyMarketBarCreationService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBar, DailyMarketBarInput
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class TwelveDataDailyMarketBarIngestionService:
    provider: DailyMarketDataProvider
    unit_of_work_factory: UnitOfWorkFactory
    creation_service: DailyMarketBarCreationService
    clock: Clock

    def ingest(
        self,
        command: TwelveDataDailyMarketBarIngestionCommand,
    ) -> TwelveDataIngestionResult:
        request = FetchCompletedDailyBarsRequest(
            source_code=TWELVE_DATA_SOURCE_CODE,
            symbol=command.symbol,
            adjustment_basis=command.adjustment_basis,
            as_of=self.clock.now_utc(),
            requested_session_count=command.requested_session_count,
            mic_code=command.mic_code,
            completed_through_session_date=command.completed_through_session_date,
        )
        try:
            observations = self.provider.fetch_completed_daily_bars(request)
        except TwelveDataProviderError as exc:
            return self._provider_failure(command, exc.category)
        if not observations:
            return self._result(command, TwelveDataIngestionOutcome.NO_DATA, 0, 0, 0, ())
        stored: list[DailyMarketBar] = []
        created_count = 0
        existing_count = 0
        for observation in observations:
            if not self._matches(command, observation):
                return self._result(
                    command,
                    TwelveDataIngestionOutcome.PROVIDER_ERROR,
                    len(observations),
                    created_count,
                    existing_count,
                    tuple(stored),
                    TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID.value,
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
                        TwelveDataIngestionOutcome.INGESTION_CONFLICT,
                        len(observations),
                        created_count,
                        existing_count,
                        tuple(stored),
                        "TWELVE_DATA_INGESTION_CONFLICT",
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
            TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING
            if existing_count
            else TwelveDataIngestionOutcome.COMPLETED
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
        command: TwelveDataDailyMarketBarIngestionCommand,
        source: DailyMarketBarInput,
    ) -> bool:
        return (
            source.source_code == TWELVE_DATA_SOURCE_CODE
            and source.symbol == command.symbol
            and source.adjustment_basis is command.adjustment_basis
            and source.session_date.value <= command.completed_through_session_date.value
        )

    def _provider_failure(
        self,
        command: TwelveDataDailyMarketBarIngestionCommand,
        category: TwelveDataErrorCategory,
    ) -> TwelveDataIngestionResult:
        outcomes = {
            TwelveDataErrorCategory.PROVIDER_DISABLED: (
                TwelveDataIngestionOutcome.PROVIDER_DISABLED
            ),
            TwelveDataErrorCategory.CONFIGURATION_MISSING: (
                TwelveDataIngestionOutcome.PROVIDER_CONFIGURATION_MISSING
            ),
            TwelveDataErrorCategory.DAILY_CREDIT_BUDGET_EXHAUSTED: (
                TwelveDataIngestionOutcome.CREDIT_BUDGET_EXHAUSTED
            ),
        }
        return self._result(
            command,
            outcomes.get(category, TwelveDataIngestionOutcome.PROVIDER_ERROR),
            0,
            0,
            0,
            (),
            category.value,
        )

    @staticmethod
    def _result(
        command: TwelveDataDailyMarketBarIngestionCommand,
        outcome: TwelveDataIngestionOutcome,
        fetched_count: int,
        created_count: int,
        existing_count: int,
        bars: tuple[DailyMarketBar, ...],
        safe_error_category: str | None = None,
    ) -> TwelveDataIngestionResult:
        sessions = tuple(bar.bar_input.session_date for bar in bars)
        return TwelveDataIngestionResult(
            outcome=outcome,
            summary=TwelveDataIngestionSummary(
                provider_code=TWELVE_DATA_SOURCE_CODE,
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
            bars=bars,
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
