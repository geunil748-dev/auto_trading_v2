from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import TracebackType
from uuid import UUID

import pytest

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidDailyMarketBarIDFactory
from auto_trading_v2.adapters.market_data.alpaca import (
    ALPACA_CAPABILITIES,
    AlpacaErrorCategory,
    AlpacaProviderError,
    AlpacaStockBarsParser,
)
from auto_trading_v2.application.contracts.alpaca_ingestion import (
    AlpacaDailyMarketBarIngestionCommand,
    AlpacaIngestionOutcome,
)
from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.application.daily_market_bar_errors import DailyMarketBarConflictError
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.services import (
    AlpacaDailyMarketBarIngestionService,
    DailyMarketBarCreationService,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.primitives import IdentifierFactory, SessionDate, Symbol
from tests.unit.adapters.market_data.alpaca.helpers import NOW, fetch_request


class MemoryRepository:
    def __init__(self) -> None:
        self.bars: list[DailyMarketBar] = []

    def add(self, new: NewDailyMarketBar) -> DailyMarketBar:
        if self.get_by_bar_key(new.bar_key) is not None:
            raise DuplicateRecordError("daily_market_bar", "insert", "duplicate")
        stored = new.stored(NOW + timedelta(seconds=len(self.bars) + 1))
        self.bars.append(stored)
        return stored

    def get_by_bar_key(self, bar_key: str) -> DailyMarketBar | None:
        return next((bar for bar in self.bars if bar.bar_key == bar_key), None)

    def get_by_source_identity(
        self,
        source_code: str,
        source_record_key: str,
        source_version: str,
    ) -> DailyMarketBar | None:
        return next(
            (
                bar
                for bar in self.bars
                if bar.bar_input.source_code == source_code
                and bar.bar_input.source_record_key == source_record_key
                and bar.bar_input.source_version == source_version
            ),
            None,
        )


class MemoryUnitOfWork:
    def __init__(self, repository: MemoryRepository) -> None:
        self.daily_market_bars = repository

    def __enter__(self):
        return self

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class MemoryUnitOfWorkFactory:
    def __init__(self) -> None:
        self.repository = MemoryRepository()

    def __call__(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.repository)


class FakeProvider:
    capabilities = ALPACA_CAPABILITIES

    def __init__(
        self,
        observations: tuple[DailyMarketBarInput, ...] = (),
        error: AlpacaProviderError | None = None,
    ) -> None:
        self.observations = observations
        self.error = error

    def fetch_completed_daily_bars(self, _request):
        if self.error is not None:
            raise self.error
        return self.observations


def observations(*, observed_at=NOW, close: str = "102.5"):
    return observations_for((("2026-07-17T04:00:00Z", close),), observed_at=observed_at)


def observations_for(
    rows: tuple[tuple[str, str], ...],
    *,
    observed_at=NOW,
) -> tuple[DailyMarketBarInput, ...]:
    payload_rows = [
        {
            "t": timestamp,
            "o": Decimal(close) - Decimal("1"),
            "h": Decimal(close) + Decimal("2"),
            "l": Decimal(close) - Decimal("2"),
            "c": Decimal(close),
            "v": 1000 + index,
            "n": 100,
            "vw": Decimal(close),
        }
        for index, (timestamp, close) in enumerate(rows)
    ]
    return (
        AlpacaStockBarsParser()
        .parse_page(
            {"bars": payload_rows, "symbol": "AAPL", "next_page_token": None},
            fetch_request(requested_session_count=max(1, len(rows))),
            observed_at,
        )
        .bars
    )


def command(mic_code: str = "XNGS") -> AlpacaDailyMarketBarIngestionCommand:
    return AlpacaDailyMarketBarIngestionCommand(
        symbol=Symbol("AAPL"),
        mic_code=mic_code,
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        completed_through_session_date=SessionDate.parse("2026-07-17"),
        requested_session_count=30,
    )


def service(provider: FakeProvider, factory: MemoryUnitOfWorkFactory):
    identifiers = IdentifierFactory(lambda: UUID(int=1000 + len(factory.repository.bars) + 1))
    creation = DailyMarketBarCreationService(
        factory,  # type: ignore[arg-type]
        UuidDailyMarketBarIDFactory(identifiers),
    )
    return AlpacaDailyMarketBarIngestionService(
        provider,  # type: ignore[arg-type]
        factory,  # type: ignore[arg-type]
        creation,
        FixedClock(NOW),
    )


def test_listing_mic_contract_has_no_xnas_alias() -> None:
    for mic_code in ("XNGS", "XNGM", "XNCM", "XNYS", "XASE"):
        assert command(mic_code).mic_code == mic_code
    with pytest.raises(DailyMarketBarValidationError):
        command("XNAS")


def test_create_repeat_revision_and_source_feed_summary() -> None:
    factory = MemoryUnitOfWorkFactory()
    first = service(FakeProvider(observations()), factory).ingest(command())
    available_at = first.bars[0].bar_input.available_at
    repeated = service(
        FakeProvider(observations(observed_at=NOW + timedelta(hours=1))),
        factory,
    ).ingest(command())
    revised = service(
        FakeProvider(observations(observed_at=NOW + timedelta(hours=2), close="103.5")),
        factory,
    ).ingest(command())

    assert first.outcome is AlpacaIngestionOutcome.COMPLETED
    assert first.summary.source_feed == "iex"
    assert repeated.outcome is AlpacaIngestionOutcome.COMPLETED_WITH_EXISTING
    assert repeated.bars[0].bar_input.available_at == available_at
    assert revised.outcome is AlpacaIngestionOutcome.COMPLETED
    assert len(factory.repository.bars) == 2
    assert len({bar.bar_input.source_version for bar in factory.repository.bars}) == 2


def test_mixed_created_and_existing_rows_are_reported_separately() -> None:
    factory = MemoryUnitOfWorkFactory()
    first = observations_for((("2026-07-16T04:00:00Z", "101.5"),))
    service(FakeProvider(first), factory).ingest(command())
    mixed = observations_for(
        (
            ("2026-07-16T04:00:00Z", "101.5"),
            ("2026-07-17T04:00:00Z", "102.5"),
        ),
        observed_at=NOW + timedelta(hours=1),
    )

    result = service(FakeProvider(mixed), factory).ingest(command())

    assert result.outcome is AlpacaIngestionOutcome.COMPLETED_WITH_EXISTING
    assert result.summary.created_count == 1
    assert result.summary.existing_count == 1
    assert len(factory.repository.bars) == 2


def test_unresolved_creation_conflict_returns_sanitized_outcome() -> None:
    class ConflictingCreation:
        def create(self, _command):
            raise DailyMarketBarConflictError("safe-bar-key")

    factory = MemoryUnitOfWorkFactory()
    subject = AlpacaDailyMarketBarIngestionService(
        FakeProvider(observations()),  # type: ignore[arg-type]
        factory,  # type: ignore[arg-type]
        ConflictingCreation(),  # type: ignore[arg-type]
        FixedClock(NOW),
    )

    result = subject.ingest(command())

    assert result.outcome is AlpacaIngestionOutcome.INGESTION_CONFLICT
    assert result.summary.safe_error_category == AlpacaErrorCategory.INGESTION_CONFLICT.value


@pytest.mark.parametrize(
    ("category", "outcome"),
    (
        (AlpacaErrorCategory.PROVIDER_DISABLED, AlpacaIngestionOutcome.PROVIDER_DISABLED),
        (
            AlpacaErrorCategory.CONFIGURATION_MISSING,
            AlpacaIngestionOutcome.PROVIDER_CONFIGURATION_MISSING,
        ),
        (AlpacaErrorCategory.HTTP_TIMEOUT, AlpacaIngestionOutcome.PROVIDER_ERROR),
    ),
)
def test_no_data_and_safe_provider_failures(
    category: AlpacaErrorCategory,
    outcome: AlpacaIngestionOutcome,
) -> None:
    empty = service(FakeProvider(), MemoryUnitOfWorkFactory()).ingest(command())
    assert empty.outcome is AlpacaIngestionOutcome.NO_DATA
    assert empty.bars == ()

    failed = service(
        FakeProvider(error=AlpacaProviderError(category)),
        MemoryUnitOfWorkFactory(),
    ).ingest(command())
    assert failed.outcome is outcome
    assert failed.summary.safe_error_category == category.value
    assert "sentinel" not in repr(failed)
