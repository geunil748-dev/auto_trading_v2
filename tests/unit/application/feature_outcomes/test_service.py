from datetime import UTC, date, datetime, timedelta

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.market_calendar import StaticOfficialUsEquityCalendar2026
from auto_trading_v2.application.contracts.feature_outcomes import (
    DailyFeatureOutcomeObservationExecutionOutcome,
    ObserveDailyFeatureScoringOutcomesCommand,
)
from auto_trading_v2.application.contracts.feature_scoring import (
    RunDailyFeatureScoringCommand,
)
from auto_trading_v2.application.services.daily_feature_outcome_observation import (
    DailyFeatureOutcomeObservationService,
)
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcomeObservationRunItemOutcome,
    DailyFeatureOutcomeObservationRunStatus,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineItemOutcome
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from tests.unit.application.feature_scoring.fakes import service_context
from tests.unit.domain.feature_outcomes.helpers import outcome_bar

from .fakes import (
    FakeBarRepository,
    FakeFeatureRepository,
    FakeOutcomeRepository,
    FakePipelineRepository,
    FakeScoringRepository,
    FakeUnitOfWorkFactory,
    OutcomeIDs,
    RunIDs,
    RunItemIDs,
)

OBSERVATION_AS_OF = datetime(2026, 8, 4, tzinfo=UTC)


def _source(
    specs: tuple[tuple[str, DailyFeaturePipelineItemOutcome], ...],
) -> tuple[object, object, dict[object, object]]:
    context = service_context(specs)
    pipeline = context.factory.pipeline.aggregate
    assert pipeline is not None
    scoring = context.service.run(
        RunDailyFeatureScoringCommand(pipeline.run.daily_feature_pipeline_run_id)
    ).result
    assert scoring is not None
    return scoring, pipeline, context.factory.features.snapshots


def _service(
    scoring: object,
    pipeline: object,
    snapshots: dict[object, object],
    bars: dict[str, tuple[object, ...]],
) -> tuple[DailyFeatureOutcomeObservationService, FakeUnitOfWorkFactory]:
    factory = FakeUnitOfWorkFactory(
        FakeScoringRepository(scoring),  # type: ignore[arg-type]
        FakePipelineRepository(pipeline),  # type: ignore[arg-type]
        FakeFeatureRepository(snapshots),  # type: ignore[arg-type]
        FakeBarRepository(bars),  # type: ignore[arg-type]
        FakeOutcomeRepository(),
    )
    service = DailyFeatureOutcomeObservationService(
        factory,  # type: ignore[arg-type]
        StaticOfficialUsEquityCalendar2026(),
        FixedClock(OBSERVATION_AS_OF + timedelta(seconds=1)),
        OutcomeIDs(),
        RunIDs(),
        RunItemIDs(),
    )
    return service, factory


def _command(scoring: object, *, as_of: datetime = OBSERVATION_AS_OF) -> object:
    return ObserveDailyFeatureScoringOutcomesCommand(
        scoring.run.daily_feature_scoring_run_id,  # type: ignore[union-attr]
        as_of,
        CompletionGracePeriod(timedelta(minutes=15)),
    )


def test_created_mixed_audit_and_exact_retry_skips_source_and_bar_reads() -> None:
    scoring, pipeline, snapshots = _source(
        (
            ("AAPL", DailyFeaturePipelineItemOutcome.READY),
            ("NVDA", DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT),
        )
    )
    bar = outcome_bar(
        1,
        close="105",
        high="110",
        low="95",
        session_date=date(2026, 8, 3),
        available_at=datetime(2026, 8, 3, 22, tzinfo=UTC),
    )
    service, factory = _service(scoring, pipeline, snapshots, {"AAPL": (bar,)})
    command = _command(scoring)

    created = service.observe(command)  # type: ignore[arg-type]
    reads = (factory.scoring.reads, factory.pipeline.reads, factory.bars.reads)
    commits = factory.commits
    retried = service.observe(command)  # type: ignore[arg-type]

    assert created.outcome is DailyFeatureOutcomeObservationExecutionOutcome.CREATED
    assert created.result is not None
    assert created.result.run.status is DailyFeatureOutcomeObservationRunStatus.COMPLETED
    assert [item.outcome for item in created.result.items] == [
        DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED,
        DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_ITEM_NOT_ELIGIBLE,
    ]
    outcome = next(iter(factory.outcomes.values.values()))
    assert outcome.forward_close_return.value > 0
    assert outcome.observation_mode is OutcomeObservationMode.PROSPECTIVE
    assert factory.bars.reads == 1
    assert factory.outcomes.inserts == 1
    assert factory.runs.inserts == 1
    assert factory.commits == 2
    assert retried.outcome is DailyFeatureOutcomeObservationExecutionOutcome.ALREADY_EXISTS
    assert retried.result == created.result
    assert (factory.scoring.reads, factory.pipeline.reads, factory.bars.reads) == reads
    assert factory.commits == commits


def test_later_observation_reuses_unchanged_immutable_outcome() -> None:
    scoring, pipeline, snapshots = _source((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    bar = outcome_bar(
        1,
        close="105",
        session_date=date(2026, 8, 3),
        available_at=datetime(2026, 8, 3, 22, tzinfo=UTC),
    )
    service, factory = _service(scoring, pipeline, snapshots, {"AAPL": (bar,)})

    first = service.observe(_command(scoring))  # type: ignore[arg-type]
    later = service.observe(  # type: ignore[arg-type]
        _command(scoring, as_of=OBSERVATION_AS_OF + timedelta(seconds=1))
    )

    assert first.result is not None
    assert later.result is not None
    assert later.result.run.outcome_existing_count == 1
    assert later.result.items[0].outcome is (
        DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_ALREADY_EXISTS
    )
    assert factory.outcomes.inserts == 1
    assert factory.runs.inserts == 2


def test_not_matured_audits_without_bar_query_or_canonical_outcome() -> None:
    scoring, pipeline, snapshots = _source((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    service, factory = _service(scoring, pipeline, snapshots, {})
    early = datetime(2026, 8, 3, 19, tzinfo=UTC)

    result = service.observe(_command(scoring, as_of=early))  # type: ignore[arg-type]

    assert result.result is not None
    assert result.result.run.status is (
        DailyFeatureOutcomeObservationRunStatus.COMPLETED_WITH_PENDING
    )
    assert result.result.items[0].outcome is (
        DailyFeatureOutcomeObservationRunItemOutcome.NOT_MATURED
    )
    assert factory.bars.reads == 0
    assert factory.outcomes.inserts == 0
    assert factory.runs.inserts == 1
    assert factory.commits == 1


def test_missing_source_run_creates_and_commits_nothing() -> None:
    scoring, pipeline, snapshots = _source((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    service, factory = _service(scoring, pipeline, snapshots, {})
    factory.scoring.aggregate = None

    result = service.observe(_command(scoring))  # type: ignore[arg-type]

    assert result.outcome is (
        DailyFeatureOutcomeObservationExecutionOutcome.SOURCE_SCORING_RUN_NOT_FOUND
    )
    assert result.result is None
    assert factory.bars.reads == 0
    assert factory.outcomes.inserts == 0
    assert factory.runs.inserts == 0
    assert factory.commits == 0
