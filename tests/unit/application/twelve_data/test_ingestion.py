from __future__ import annotations

from datetime import datetime, timedelta
from types import TracebackType
from uuid import UUID

import pytest

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidDailyMarketBarIDFactory
from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_CAPABILITIES,
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)
from auto_trading_v2.adapters.market_data.twelve_data.parser import (
    TwelveDataTimeSeriesParser,
)
from auto_trading_v2.application.contracts.daily_market_bars import NewDailyMarketBar
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionCommand,
    TwelveDataIngestionOutcome,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.services import (
    DailyMarketBarCalendarValidator,
    DailyMarketBarCreationService,
    TwelveDataDailyMarketBarIngestionService,
)
from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
    DailyMarketBarInput,
    DailyMarketBarValidationError,
)
from auto_trading_v2.domain.market_calendar import ProviderBarCalendarErrorCategory
from auto_trading_v2.domain.primitives import (
    IdentifierFactory,
    SessionDate,
    Symbol,
)
from tests.unit.adapters.market_data.twelve_data.helpers import (
    NOW,
    fetch_request,
    payload,
    row,
)


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
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

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
        self.units: list[MemoryUnitOfWork] = []

    def __call__(self) -> MemoryUnitOfWork:
        unit = MemoryUnitOfWork(self.repository)
        self.units.append(unit)
        return unit


class FakeProvider:
    capabilities = TWELVE_DATA_CAPABILITIES

    def __init__(
        self,
        observations: tuple[DailyMarketBarInput, ...] = (),
        error: TwelveDataProviderError | None = None,
    ) -> None:
        self.observations = observations
        self.error = error
        self.requests = []

    def fetch_completed_daily_bars(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.observations


def observations(
    *,
    observed_at: datetime = NOW,
    values: list[dict[str, object]] | None = None,
) -> tuple[DailyMarketBarInput, ...]:
    request = fetch_request(requested_session_count=30)
    return TwelveDataTimeSeriesParser().parse(
        payload(values=values),
        request,
        observed_at,
    )


def command(
    count: int = 30,
    mic_code: str = "XNGS",
) -> TwelveDataDailyMarketBarIngestionCommand:
    return TwelveDataDailyMarketBarIngestionCommand(
        symbol=Symbol("AAPL"),
        mic_code=mic_code,
        adjustment_basis=DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        completed_through_session_date=SessionDate.parse("2026-07-01"),
        requested_session_count=count,
    )


@pytest.mark.parametrize("mic_code", ("XNGS", "XNGM", "XNCM", "XNYS", "XASE"))
def test_listing_mic_contract_is_explicit(mic_code: str) -> None:
    assert command(mic_code=mic_code).mic_code == mic_code


def test_operating_mic_is_not_implicitly_aliased() -> None:
    with pytest.raises(DailyMarketBarValidationError):
        command(mic_code="XNAS")


def service(
    provider: FakeProvider,
    factory: MemoryUnitOfWorkFactory,
) -> TwelveDataDailyMarketBarIngestionService:
    identifiers = IdentifierFactory(lambda: UUID(int=1000 + len(factory.repository.bars) + 1))
    creation = DailyMarketBarCreationService(
        factory,  # type: ignore[arg-type]
        UuidDailyMarketBarIDFactory(identifiers),
    )
    return TwelveDataDailyMarketBarIngestionService(
        provider,  # type: ignore[arg-type]
        factory,  # type: ignore[arg-type]
        creation,
        FixedClock(NOW),
        DailyMarketBarCalendarValidator(StaticOfficialUsEquityCalendar2026()),
    )


def test_completed_creates_each_canonical_bar() -> None:
    factory = MemoryUnitOfWorkFactory()
    subject = service(FakeProvider(observations()), factory)

    result = subject.ingest(command())

    assert result.outcome is TwelveDataIngestionOutcome.COMPLETED
    assert result.summary.fetched_count == 3
    assert result.summary.created_count == 3
    assert result.summary.existing_count == 0
    assert len(factory.repository.bars) == 3
    assert all(bar.bar_input.volume is None for bar in result.bars)


def test_calendar_failure_stops_before_persistence() -> None:
    factory = MemoryUnitOfWorkFactory()
    holiday = observations(values=[row("2026-06-19", "100")])

    result = service(FakeProvider(holiday), factory).ingest(command())

    assert result.outcome is TwelveDataIngestionOutcome.PROVIDER_ERROR
    assert result.summary.safe_error_category == (
        ProviderBarCalendarErrorCategory.ON_NON_TRADING_DAY.value
    )
    assert factory.repository.bars == []
    assert factory.units == []


def test_same_content_refetch_preserves_first_available_at() -> None:
    factory = MemoryUnitOfWorkFactory()
    first_provider = FakeProvider(observations())
    first = service(first_provider, factory).ingest(command())
    original_available = tuple(bar.bar_input.available_at for bar in first.bars)
    later = observations(observed_at=NOW + timedelta(hours=4))

    repeated = service(FakeProvider(later), factory).ingest(command())

    assert repeated.outcome is TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING
    assert repeated.summary.created_count == 0
    assert repeated.summary.existing_count == 3
    assert tuple(bar.bar_input.available_at for bar in repeated.bars) == original_available
    assert len(factory.repository.bars) == 3


def test_provider_content_change_creates_new_immutable_revision() -> None:
    factory = MemoryUnitOfWorkFactory()
    first = observations(values=[row("2026-07-01", "100")])
    service(FakeProvider(first), factory).ingest(command(1))
    revised = observations(
        observed_at=NOW + timedelta(hours=1),
        values=[row("2026-07-01", "101")],
    )

    result = service(FakeProvider(revised), factory).ingest(command(1))

    assert result.outcome is TwelveDataIngestionOutcome.COMPLETED
    assert result.summary.created_count == 1
    assert len(factory.repository.bars) == 2
    assert len({bar.bar_input.source_version for bar in factory.repository.bars}) == 2


def test_no_data_has_safe_empty_summary() -> None:
    result = service(FakeProvider(), MemoryUnitOfWorkFactory()).ingest(command())

    assert result.outcome is TwelveDataIngestionOutcome.NO_DATA
    assert result.summary.fetched_count == 0
    assert result.summary.oldest_session_date is None
    assert result.bars == ()


@pytest.mark.parametrize(
    ("category", "outcome"),
    (
        (
            TwelveDataErrorCategory.PROVIDER_DISABLED,
            TwelveDataIngestionOutcome.PROVIDER_DISABLED,
        ),
        (
            TwelveDataErrorCategory.CONFIGURATION_MISSING,
            TwelveDataIngestionOutcome.PROVIDER_CONFIGURATION_MISSING,
        ),
        (
            TwelveDataErrorCategory.DAILY_CREDIT_BUDGET_EXHAUSTED,
            TwelveDataIngestionOutcome.CREDIT_BUDGET_EXHAUSTED,
        ),
        (
            TwelveDataErrorCategory.HTTP_TIMEOUT,
            TwelveDataIngestionOutcome.PROVIDER_ERROR,
        ),
    ),
)
def test_provider_failures_return_sanitized_outcomes(
    category: TwelveDataErrorCategory,
    outcome: TwelveDataIngestionOutcome,
) -> None:
    error = TwelveDataProviderError(category)

    result = service(
        FakeProvider(error=error),
        MemoryUnitOfWorkFactory(),
    ).ingest(command())

    assert result.outcome is outcome
    assert result.summary.safe_error_category == category.value
    assert "apikey" not in repr(result)
