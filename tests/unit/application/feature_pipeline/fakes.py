from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.adapters.market_data.twelve_data import (
    TWELVE_DATA_SOURCE_CODE,
)
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    RunDailyFeaturePipelineCommand,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataIngestionOutcome,
    TwelveDataIngestionResult,
    TwelveDataIngestionSummary,
)
from auto_trading_v2.application.feature_building import (
    DailyTechnicalFeatureSnapshotBuildOutcome,
    DailyTechnicalFeatureSnapshotBuildResult,
)
from auto_trading_v2.application.ports.batch_budget import (
    DailyMarketDataBatchBudgetPort,
    DailyMarketDataProviderRole,
)
from auto_trading_v2.application.ports.id_factory import (
    DailyFeaturePipelineItemIDFactory,
    DailyFeaturePipelineRunIDFactory,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.completed_daily_bars_request import (
    CompletedDailyBarsRequestFactory,
)
from auto_trading_v2.application.services.completed_session import (
    UsEquityCompletedSessionResolver,
)
from auto_trading_v2.application.services.daily_feature_pipeline import (
    DailyFeaturePipelineService,
)
from auto_trading_v2.application.services.daily_technical_feature_snapshot import (
    DailyTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionService,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from auto_trading_v2.domain.primitives import (
    FeatureSnapshotID,
    Symbol,
    UniverseSnapshotID,
)
from auto_trading_v2.domain.universes import (
    UniverseCode,
    UniverseDefinition,
    UniverseMember,
    UniverseSnapshot,
    UniverseVersion,
    universe_content_digest,
    universe_key,
)
from auto_trading_v2.ports.clock import Clock

from .repository_fakes import (
    CountingItemIDs,
    CountingRunIDs,
    FakeUnitOfWorkFactory,
)

NOW = datetime(2026, 8, 1, 0, tzinfo=UTC)


@dataclass
class FixedClock:
    value: datetime = NOW

    def now_utc(self) -> datetime:
        return self.value


@dataclass
class FakeBudget:
    provider_code: str = TWELVE_DATA_SOURCE_CODE
    provider_role: DailyMarketDataProviderRole = DailyMarketDataProviderRole.PRIMARY_FEATURE_SOURCE
    enabled: bool = True
    configured: bool = True
    maximum_rows_per_request: int | None = 5000
    daily_available: int | None = 100
    minute_available: int | None = 8
    consumed: int | None = 0
    estimated_multiplier: int = 1

    def estimate_maximum_cost(self, member_count: int, requested: int) -> int | None:
        if self.maximum_rows_per_request is None or requested > self.maximum_rows_per_request:
            return None
        return member_count * self.estimated_multiplier

    def available_daily_budget(self) -> int | None:
        return self.daily_available

    def available_minute_budget(self) -> int | None:
        return self.minute_available

    def consumed_daily_credits(self) -> int | None:
        return self.consumed


@dataclass(frozen=True)
class FakeSnapshotInput:
    quality_status: FeatureQualityStatus


@dataclass(frozen=True)
class FakeSnapshot:
    feature_snapshot_id: FeatureSnapshotID
    snapshot_input: FakeSnapshotInput


@dataclass
class ScriptedFeatureService:
    scripts: dict[str, FeatureQualityStatus | None] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def build(self, command: Any) -> DailyTechnicalFeatureSnapshotBuildResult:
        symbol = command.symbol.value
        self.calls.append(symbol)
        quality = self.scripts.get(symbol, FeatureQualityStatus.READY)
        if quality is None:
            return DailyTechnicalFeatureSnapshotBuildResult(
                DailyTechnicalFeatureSnapshotBuildOutcome.DATA_INSUFFICIENT,
                None,
                ("INSUFFICIENT_COMPLETED_DAILY_BARS",),
            )
        snapshot = FakeSnapshot(
            FeatureSnapshotID(UUID(int=1000 + len(self.calls))),
            FakeSnapshotInput(quality),
        )
        return DailyTechnicalFeatureSnapshotBuildResult(
            DailyTechnicalFeatureSnapshotBuildOutcome.CREATED,
            cast(Any, snapshot),
        )


@dataclass
class ScriptedIngestionService:
    budget: FakeBudget
    scripts: dict[str, tuple[TwelveDataIngestionOutcome, str | None]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    source_codes: list[str] = field(default_factory=list)

    def ingest_request(self, command: Any, request: Any) -> TwelveDataIngestionResult:
        symbol = command.symbol.value
        self.calls.append(symbol)
        self.source_codes.append(request.source_code)
        if self.budget.consumed is not None:
            self.budget.consumed += 1
        outcome, reason = self.scripts.get(
            symbol,
            (TwelveDataIngestionOutcome.COMPLETED, None),
        )
        completed = outcome in {
            TwelveDataIngestionOutcome.COMPLETED,
            TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING,
        }
        return TwelveDataIngestionResult(
            outcome,
            TwelveDataIngestionSummary(
                TWELVE_DATA_SOURCE_CODE,
                command.symbol,
                command.mic_code,
                command.adjustment_basis,
                command.completed_through_session_date,
                21 if completed else 0,
                21 if outcome is TwelveDataIngestionOutcome.COMPLETED else 0,
                21 if outcome is TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING else 0,
                None,
                command.completed_through_session_date if completed else None,
                reason,
            ),
        )


def universe(*symbols: str) -> UniverseSnapshot:
    definition = UniverseDefinition(
        UniverseCode("P3_TEST"),
        UniverseVersion("v1"),
        tuple(UniverseMember(Symbol(symbol), "XNGS") for symbol in symbols),
    )
    return UniverseSnapshot(
        UniverseSnapshotID(UUID(int=100)),
        universe_key(definition),
        universe_content_digest(definition),
        definition,
        NOW,
        NOW,
    )


def command(snapshot: UniverseSnapshot, *, as_of: datetime = NOW) -> RunDailyFeaturePipelineCommand:
    return RunDailyFeaturePipelineCommand(
        snapshot.universe_snapshot_id,
        TWELVE_DATA_SOURCE_CODE,
        as_of,
        CompletionGracePeriod(timedelta(minutes=15)),
        TradingDayHorizon(1),
        30,
    )


@dataclass
class ServiceContext:
    service: DailyFeaturePipelineService
    factory: FakeUnitOfWorkFactory
    budget: FakeBudget
    ingestion: ScriptedIngestionService
    features: ScriptedFeatureService
    run_ids: CountingRunIDs
    item_ids: CountingItemIDs


def service(snapshot: UniverseSnapshot, budget: FakeBudget | None = None) -> ServiceContext:
    actual_budget = FakeBudget() if budget is None else budget
    ingestion = ScriptedIngestionService(actual_budget)
    features = ScriptedFeatureService()
    factory = FakeUnitOfWorkFactory(snapshot)
    run_ids = CountingRunIDs()
    item_ids = CountingItemIDs()
    clock = FixedClock()
    target = DailyFeaturePipelineService(
        cast(UnitOfWorkFactory, factory),
        CompletedDailyBarsRequestFactory(
            UsEquityCompletedSessionResolver(StaticOfficialUsEquityCalendar2026())
        ),
        cast(DailyMarketDataBatchBudgetPort, actual_budget),
        cast(TwelveDataDailyMarketBarIngestionService, ingestion),
        cast(DailyTechnicalFeatureSnapshotService, features),
        cast(Clock, clock),
        cast(DailyFeaturePipelineRunIDFactory, run_ids),
        cast(DailyFeaturePipelineItemIDFactory, item_ids),
    )
    return ServiceContext(
        target,
        factory,
        actual_budget,
        ingestion,
        features,
        run_ids,
        item_ids,
    )
