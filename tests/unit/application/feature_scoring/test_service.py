from types import MappingProxyType

import pytest

from auto_trading_v2.application.contracts.feature_scoring import (
    DailyFeatureScoringExecutionOutcome,
    RunDailyFeatureScoringCommand,
)
from auto_trading_v2.application.feature_scoring_errors import (
    DailyFeatureScoringConflictError,
)
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
)
from auto_trading_v2.domain.feature_scoring import (
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRunStatus,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus

from .fakes import FakePipelineRepository, service_context, snapshot


def command(context: object) -> RunDailyFeatureScoringCommand:
    source = context.factory.pipeline.aggregate  # type: ignore[union-attr]
    assert source is not None
    return RunDailyFeatureScoringCommand(source.run.daily_feature_pipeline_run_id)


def test_created_mixed_population_quality_ranking_and_exact_retry() -> None:
    context = service_context(
        (
            ("AAPL", DailyFeaturePipelineItemOutcome.READY),
            ("MSFT", DailyFeaturePipelineItemOutcome.READY),
            ("NVDA", DailyFeaturePipelineItemOutcome.DEGRADED),
            ("AMZN", DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT),
            ("META", DailyFeaturePipelineItemOutcome.PROVIDER_ERROR),
        )
    )
    target = command(context)

    first = context.service.run(target)
    feature_reads = context.factory.features.calls
    aggregate_reads = context.factory.pipeline.aggregate_calls
    id_calls = (context.run_ids.calls, context.item_ids.calls)
    retry = context.service.run(target)

    assert first.outcome is DailyFeatureScoringExecutionOutcome.CREATED
    assert first.result is not None
    assert first.result.run.status is DailyFeatureScoringRunStatus.COMPLETED_WITH_UNSCORABLE
    assert (
        first.result.run.scored_ready_count,
        first.result.run.scored_degraded_count,
        first.result.run.unscorable_count,
    ) == (2, 1, 2)
    assert [item.outcome for item in first.result.items] == [
        DailyFeatureScoringItemOutcome.SCORED_READY,
        DailyFeatureScoringItemOutcome.SCORED_READY,
        DailyFeatureScoringItemOutcome.SCORED_DEGRADED,
        DailyFeatureScoringItemOutcome.SOURCE_ITEM_NOT_SCORABLE,
        DailyFeatureScoringItemOutcome.SOURCE_ITEM_NOT_SCORABLE,
    ]
    assert [item.rank for item in first.result.items] == [2, 1, 3, None, None]
    assert first.result.items[2].volume_score is None
    assert retry.outcome is DailyFeatureScoringExecutionOutcome.ALREADY_EXISTS
    assert retry.result == first.result
    assert context.factory.features.calls == feature_reads
    assert context.factory.pipeline.aggregate_calls == aggregate_reads
    assert (context.run_ids.calls, context.item_ids.calls) == id_calls
    assert context.factory.scoring.add_calls == 1
    assert context.factory.commits == 1


def test_source_run_missing_and_not_eligible_create_nothing() -> None:
    context = service_context((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    target = command(context)
    context.factory.pipeline = FakePipelineRepository(None)

    missing = context.service.run(target)

    assert missing.outcome is DailyFeatureScoringExecutionOutcome.SOURCE_RUN_NOT_FOUND
    assert missing.result is None
    assert context.factory.scoring.add_calls == 0
    assert context.factory.commits == 0

    blocked = service_context(
        (("AAPL", DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET),),
        status=DailyFeaturePipelineRunStatus.BUDGET_BLOCKED,
    )
    ineligible = blocked.service.run(command(blocked))
    assert ineligible.outcome is DailyFeatureScoringExecutionOutcome.SOURCE_RUN_NOT_ELIGIBLE
    assert blocked.factory.pipeline.aggregate_calls == 0
    assert blocked.factory.features.calls == 0
    assert blocked.factory.commits == 0


def test_missing_snapshot_is_audited_without_scoring() -> None:
    context = service_context((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    context.factory.features.snapshots.clear()

    result = context.service.run(command(context))

    assert result.result is not None
    assert result.result.run.status is DailyFeatureScoringRunStatus.NO_SCORABLE_ITEMS
    assert result.result.items[0].outcome is DailyFeatureScoringItemOutcome.FEATURE_SNAPSHOT_MISSING
    assert result.result.items[0].rank is None
    assert result.result.items[0].overall_relative_score is None


def test_source_quality_mismatch_is_not_scored() -> None:
    context = service_context((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    aggregate = context.factory.pipeline.aggregate
    assert aggregate is not None
    original = aggregate.items[0]
    assert original.feature_snapshot_id is not None
    context.factory.features.snapshots[original.feature_snapshot_id.value] = snapshot(
        identifier=original.feature_snapshot_id.value.int,
        symbol="AAPL",
        quality=FeatureQualityStatus.DEGRADED,
    )

    result = context.service.run(command(context))

    assert result.result is not None
    assert result.result.items[0].outcome is DailyFeatureScoringItemOutcome.FEATURE_SOURCE_MISMATCH
    assert result.result.items[0].safe_reason_code == "FEATURE_SOURCE_MISMATCH"


def test_policy_values_are_fixed_at_command_boundary() -> None:
    context = service_context((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    source = context.factory.pipeline.aggregate
    assert source is not None

    try:
        RunDailyFeatureScoringCommand(
            source.run.daily_feature_pipeline_run_id,
            scoring_policy_version="v2",
        )
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unsupported P4A policy was accepted")


def test_feature_contract_invalid_and_quality_unsupported_are_item_local() -> None:
    invalid = service_context((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    invalid_snapshot = next(iter(invalid.factory.features.snapshots.values()))
    object.__setattr__(
        invalid_snapshot.snapshot_input,
        "feature_values",
        MappingProxyType(
            {
                key: value
                for key, value in invalid_snapshot.snapshot_input.feature_values.items()
                if key != "one_day_return"
            }
        ),
    )

    invalid_result = invalid.service.run(command(invalid))

    assert invalid_result.result is not None
    assert invalid_result.result.items[0].outcome is (
        DailyFeatureScoringItemOutcome.FEATURE_CONTRACT_INVALID
    )
    unsupported = service_context((("AAPL", DailyFeaturePipelineItemOutcome.DEGRADED),))
    unsupported_snapshot = next(iter(unsupported.factory.features.snapshots.values()))
    object.__setattr__(
        unsupported_snapshot.snapshot_input,
        "quality_reason_codes",
        ("PRICE_DATA_INCOMPLETE",),
    )

    unsupported_result = unsupported.service.run(command(unsupported))

    assert unsupported_result.result is not None
    assert unsupported_result.result.items[0].outcome is (
        DailyFeatureScoringItemOutcome.FEATURE_QUALITY_UNSUPPORTED
    )


def test_unique_race_same_digest_rereads_and_returns_already_exists() -> None:
    context = service_context((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    context.factory.scoring.duplicate_on_add = True

    result = context.service.run(command(context))

    assert result.outcome is DailyFeatureScoringExecutionOutcome.ALREADY_EXISTS
    assert result.result is not None
    assert context.factory.rollbacks == 1
    assert context.factory.commits == 0
    assert context.factory.scoring.add_calls == 1


def test_unique_race_different_digest_raises_sanitized_conflict() -> None:
    context = service_context((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    context.factory.scoring.duplicate_on_add = True
    context.factory.scoring.conflicting_digest = True

    with pytest.raises(DailyFeatureScoringConflictError) as captured:
        context.service.run(command(context))

    assert str(captured.value) == "daily feature scoring content conflict"
    assert context.factory.rollbacks == 1
