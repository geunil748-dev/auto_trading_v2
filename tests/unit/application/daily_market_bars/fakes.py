from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.daily_market_bars import (
    CreateDailyMarketBarCommand,
    NewDailyMarketBar,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from auto_trading_v2.domain.primitives import DailyMarketBarID
from tests.unit.domain.daily_market_bars.helpers import bar_input

RECORDED_AT = datetime(2026, 2, 1, tzinfo=UTC)


def command(**changes: object) -> CreateDailyMarketBarCommand:
    source = bar_input()
    values = {name: getattr(source, name) for name in source.__dataclass_fields__}
    values.update(changes)
    return CreateDailyMarketBarCommand(**values)


def stored(source: CreateDailyMarketBarCommand, identifier: int = 1) -> DailyMarketBar:
    return NewDailyMarketBar(
        DailyMarketBarID(UUID(int=identifier)),
        daily_market_bar_key(source.bar_input),
        daily_market_bar_content_digest(source.bar_input),
        source.bar_input,
    ).stored(RECORDED_AT)


class RecordingIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> DailyMarketBarID:
        self.calls += 1
        return DailyMarketBarID(UUID(int=100 + self.calls))


class FakeDailyMarketBarRepository:
    def __init__(
        self,
        existing: DailyMarketBar | None = None,
        *,
        duplicate_on_add: bool = False,
    ) -> None:
        self.existing = existing
        self.duplicate_on_add = duplicate_on_add
        self.add_calls: list[NewDailyMarketBar] = []
        self.get_calls: list[str] = []

    def get_by_bar_key(self, bar_key: str) -> DailyMarketBar | None:
        self.get_calls.append(bar_key)
        if self.existing is not None and self.existing.bar_key == bar_key:
            return self.existing
        return None

    def add(self, bar: NewDailyMarketBar) -> DailyMarketBar:
        self.add_calls.append(bar)
        if self.duplicate_on_add:
            raise DuplicateRecordError(
                entity="daily_market_bar",
                operation="insert",
                reason="duplicate_record",
            )
        self.existing = bar.stored(RECORDED_AT)
        return self.existing


class FakeUnitOfWork:
    def __init__(self, repository: FakeDailyMarketBarRepository) -> None:
        self.daily_market_bars = repository
        self.commit_calls = 0
        self.rollback_calls = 0
        self.exit_calls = 0

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_calls += 1


class SequencedUnitOfWorkFactory:
    def __init__(self, *units: FakeUnitOfWork) -> None:
        self.units = list(units)
        self.calls = 0

    def __call__(self) -> FakeUnitOfWork:
        unit = self.units[self.calls]
        self.calls += 1
        return unit
