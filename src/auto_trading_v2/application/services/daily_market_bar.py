"""Atomic idempotent creation of immutable DailyMarketBar records."""

from dataclasses import dataclass

from auto_trading_v2.application.contracts.daily_market_bars import (
    CreateDailyMarketBarCommand,
    DailyMarketBarCreationOutcome,
    DailyMarketBarCreationResult,
    NewDailyMarketBar,
)
from auto_trading_v2.application.daily_market_bar_errors import (
    DailyMarketBarConflictError,
    DailyMarketBarRaceResolutionError,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.ports.id_factory import DailyMarketBarIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarValidationError,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)


@dataclass(frozen=True, slots=True)
class DailyMarketBarCreationService:
    unit_of_work_factory: UnitOfWorkFactory
    daily_market_bar_id_factory: DailyMarketBarIDFactory

    def create(self, command: CreateDailyMarketBarCommand) -> DailyMarketBarCreationResult:
        if not isinstance(command, CreateDailyMarketBarCommand):
            raise DailyMarketBarValidationError("DailyMarketBar 생성 command가 필요합니다.")
        bar_input = command.bar_input
        bar_key = daily_market_bar_key(bar_input)
        content_digest = daily_market_bar_content_digest(bar_input)
        raced = False
        with self.unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.daily_market_bars.get_by_bar_key(bar_key)
            if existing is not None:
                return self._existing(existing, content_digest)
            new_bar = NewDailyMarketBar(
                self.daily_market_bar_id_factory.new(),
                bar_key,
                content_digest,
                bar_input,
            )
            try:
                stored = unit_of_work.daily_market_bars.add(new_bar)
            except DuplicateRecordError:
                unit_of_work.rollback()
                raced = True
            else:
                unit_of_work.commit()
                return DailyMarketBarCreationResult(
                    DailyMarketBarCreationOutcome.CREATED,
                    stored,
                )
        if not raced:
            raise DailyMarketBarRaceResolutionError()
        return self._resolve_race(bar_key, content_digest)

    def _resolve_race(
        self,
        bar_key: str,
        content_digest: str,
    ) -> DailyMarketBarCreationResult:
        with self.unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.daily_market_bars.get_by_bar_key(bar_key)
            if existing is None:
                raise DailyMarketBarRaceResolutionError()
            return self._existing(existing, content_digest)

    @staticmethod
    def _existing(
        existing: DailyMarketBar,
        content_digest: str,
    ) -> DailyMarketBarCreationResult:
        if existing.content_digest != content_digest:
            raise DailyMarketBarConflictError(existing.bar_key)
        return DailyMarketBarCreationResult(
            DailyMarketBarCreationOutcome.ALREADY_EXISTS,
            existing,
        )
