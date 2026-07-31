from datetime import timedelta
from itertools import count
from uuid import UUID

import pytest
from sqlalchemy import func, select

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import (
    UuidDailyFeaturePipelineItemIDFactory,
    UuidDailyFeaturePipelineRunIDFactory,
    UuidDailyMarketBarIDFactory,
    UuidFeatureSnapshotIDFactory,
)
from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import (
    paper_orders,
    recommendations,
    trade_intents,
)
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    DailyFeaturePipelineExecutionOutcome,
    RunDailyFeaturePipelineCommand,
)
from auto_trading_v2.application.services import (
    CompletedDailyBarsRequestFactory,
    DailyFeaturePipelineService,
    DailyMarketBarCalendarValidator,
    DailyMarketBarCreationService,
    DailyTechnicalFeatureSnapshotService,
    FeatureSnapshotCreationService,
    TwelveDataDailyMarketBarIngestionService,
    UsEquityCompletedSessionResolver,
)
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
)
from auto_trading_v2.domain.feature_snapshots import (
    FeatureQualityStatus,
    TradingDayHorizon,
)
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from auto_trading_v2.domain.primitives import IdentifierFactory
from tests.integration.feature_pipeline.helpers import NOW, universe_command, universe_service
from tests.integration.feature_pipeline.scripted import (
    ScriptedBatchBudget,
    ScriptedMultiSymbolProvider,
)

pytestmark = pytest.mark.integration


def test_scripted_three_symbol_pipeline_isolated_retry_and_dotnet_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    calendar = StaticOfficialUsEquityCalendar2026()
    clock = FixedClock(NOW)
    budget = ScriptedBatchBudget()
    provider = ScriptedMultiSymbolProvider(budget, calendar)
    identifiers = count(800_000)
    id_policy = IdentifierFactory(lambda: UUID(int=next(identifiers)))
    ingestion = TwelveDataDailyMarketBarIngestionService(
        provider,
        sqlalchemy_uow_factory,
        DailyMarketBarCreationService(
            sqlalchemy_uow_factory,
            UuidDailyMarketBarIDFactory(id_policy),
        ),
        clock,
        DailyMarketBarCalendarValidator(calendar),
    )
    features = DailyTechnicalFeatureSnapshotService(
        sqlalchemy_uow_factory,
        FeatureSnapshotCreationService(
            sqlalchemy_uow_factory,
            FixedClock(NOW + timedelta(seconds=1)),
            UuidFeatureSnapshotIDFactory(id_policy),
        ),
    )
    snapshot = (
        universe_service(sqlalchemy_uow_factory, 801001)
        .create(universe_command(801, "NVDA", "MSFT", "AAPL"))
        .snapshot
    )
    target = DailyFeaturePipelineService(
        sqlalchemy_uow_factory,
        CompletedDailyBarsRequestFactory(UsEquityCompletedSessionResolver(calendar)),
        budget,
        ingestion,
        features,
        clock,
        UuidDailyFeaturePipelineRunIDFactory(id_policy),
        UuidDailyFeaturePipelineItemIDFactory(id_policy),
    )
    pipeline_command = RunDailyFeaturePipelineCommand(
        snapshot.universe_snapshot_id,
        "TWELVE_DATA_TIME_SERIES",
        NOW,
        CompletionGracePeriod(timedelta(minutes=15)),
        TradingDayHorizon(1),
        30,
    )

    first = target.run(pipeline_command)
    calls_after_first = tuple(provider.calls)
    retried = target.run(pipeline_command)

    assert first.result.run.status is DailyFeaturePipelineRunStatus.COMPLETED_WITH_PARTIAL_FAILURES
    assert [item.symbol.value for item in first.result.items] == ["AAPL", "MSFT", "NVDA"]
    assert [item.outcome for item in first.result.items] == [
        DailyFeaturePipelineItemOutcome.DEGRADED,
        DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT,
        DailyFeaturePipelineItemOutcome.PROVIDER_ERROR,
    ]
    assert provider.calls == ["AAPL", "MSFT", "NVDA"]
    assert retried.outcome is DailyFeaturePipelineExecutionOutcome.ALREADY_EXISTS
    assert retried.result == first.result
    assert tuple(provider.calls) == calls_after_first
    aapl = first.result.items[0]
    assert aapl.feature_snapshot_id is not None
    assert aapl.feature_quality_status is FeatureQualityStatus.DEGRADED
    with sqlalchemy_uow_factory() as reader:
        feature = reader.feature_snapshots.get_by_id(aapl.feature_snapshot_id)
    assert feature is not None
    assert feature.snapshot_input.feature_values["volume_ratio_5_to_20"] is None
    assert feature.snapshot_input.feature_values["latest_volume_to_avg20"] is None
    assert feature.snapshot_input.feature_values["average_dollar_volume_20"] is None
    with dotnet_uow_factory() as reader:
        dotnet_read = reader.daily_feature_pipeline_runs.get_run_with_items(
            first.result.run.daily_feature_pipeline_run_id
        )
    assert dotnet_read == first.result
    with sqlalchemy_uow_factory.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(recommendations)) == 0
        assert connection.scalar(select(func.count()).select_from(trade_intents)) == 0
        assert connection.scalar(select(func.count()).select_from(paper_orders)) == 0
