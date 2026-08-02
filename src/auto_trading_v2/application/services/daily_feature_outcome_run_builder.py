"""Build immutable P4B.1 observation-run audits from resolved items."""

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.ports.id_factory import (
    DailyFeatureOutcomeObservationRunIDFactory,
    DailyFeatureOutcomeObservationRunItemIDFactory,
)
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcomeObservationRun,
    DailyFeatureOutcomeObservationRunItem,
    DailyFeatureOutcomeObservationRunItemOutcome,
    DailyFeatureOutcomeObservationRunStatus,
    DailyFeatureOutcomeObservationRunWithItems,
    OutcomeObservationRunIdentity,
    daily_feature_outcome_observation_content_digest,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeObservationRunID,
    DailyFeatureScoringItemID,
    SessionDate,
)


@dataclass(frozen=True, slots=True)
class ObservationRunItemSource:
    source_item_id: DailyFeatureScoringItemID
    outcome: DailyFeatureOutcomeObservationRunItemOutcome
    outcome_id: DailyFeatureOutcomeID | None
    terminal_session_date: SessionDate | None


def build_observation_run(
    identity: OutcomeObservationRunIdentity,
    run_key: str,
    sources: tuple[ObservationRunItemSource, ...],
    generated_at: datetime,
    run_id_factory: DailyFeatureOutcomeObservationRunIDFactory,
    item_id_factory: DailyFeatureOutcomeObservationRunItemIDFactory,
) -> DailyFeatureOutcomeObservationRunWithItems:
    run_id = run_id_factory.new()
    items = tuple(
        DailyFeatureOutcomeObservationRunItem(
            item_id_factory.new(),
            run_id,
            source.source_item_id,
            ordinal,
            source.outcome,
            source.outcome_id,
            source.terminal_session_date,
            None if source.outcome_id is not None else source.outcome.value,
            generated_at,
            generated_at,
        )
        for ordinal, source in enumerate(sources, 1)
    )
    counts = _counts(items)
    status = _run_status(items)
    provisional = _run(identity, run_key, "0" * 64, status, counts, generated_at, run_id)
    digest = daily_feature_outcome_observation_content_digest(provisional, items)
    run = _run(identity, run_key, digest, status, counts, generated_at, run_id)
    return DailyFeatureOutcomeObservationRunWithItems(run, items)


def _run(
    identity: OutcomeObservationRunIdentity,
    run_key: str,
    content_digest: str,
    status: DailyFeatureOutcomeObservationRunStatus,
    counts: tuple[int, ...],
    generated_at: datetime,
    run_id: DailyFeatureOutcomeObservationRunID,
) -> DailyFeatureOutcomeObservationRun:
    return DailyFeatureOutcomeObservationRun(
        daily_feature_outcome_observation_run_id=run_id,
        observation_run_key=run_key,
        content_digest=content_digest,
        identity=identity,
        status=status,
        total_count=sum(counts),
        outcome_created_count=counts[0],
        outcome_existing_count=counts[1],
        not_matured_count=counts[2],
        incomplete_count=counts[3],
        ineligible_count=counts[4],
        invalid_count=counts[5],
        generated_at=generated_at,
        recorded_at=generated_at,
    )


def _counts(items: tuple[DailyFeatureOutcomeObservationRunItem, ...]) -> tuple[int, ...]:
    outcomes = tuple(item.outcome for item in items)
    groups = (
        {DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED},
        {DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_ALREADY_EXISTS},
        {DailyFeatureOutcomeObservationRunItemOutcome.NOT_MATURED},
        {DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BARS_INCOMPLETE},
        {DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_ITEM_NOT_ELIGIBLE},
        {
            DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_CHAIN_INVALID,
            DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BAR_CONTRACT_INVALID,
            DailyFeatureOutcomeObservationRunItemOutcome.CALENDAR_OUT_OF_COVERAGE,
        },
    )
    return tuple(sum(value in group for value in outcomes) for group in groups)


def _run_status(
    items: tuple[DailyFeatureOutcomeObservationRunItem, ...],
) -> DailyFeatureOutcomeObservationRunStatus:
    outcomes = {item.outcome for item in items}
    eligible = len(items) - sum(
        item.outcome is DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_ITEM_NOT_ELIGIBLE
        for item in items
    )
    if eligible == 0:
        return DailyFeatureOutcomeObservationRunStatus.NO_ELIGIBLE_ITEMS
    if DailyFeatureOutcomeObservationRunItemOutcome.CALENDAR_OUT_OF_COVERAGE in outcomes:
        return DailyFeatureOutcomeObservationRunStatus.CALENDAR_OUT_OF_COVERAGE
    invalid = outcomes & {
        DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_CHAIN_INVALID,
        DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BAR_CONTRACT_INVALID,
    }
    if invalid:
        return DailyFeatureOutcomeObservationRunStatus.COMPLETED_WITH_GAPS
    pending = outcomes & {
        DailyFeatureOutcomeObservationRunItemOutcome.NOT_MATURED,
        DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BARS_INCOMPLETE,
    }
    return (
        DailyFeatureOutcomeObservationRunStatus.COMPLETED_WITH_PENDING
        if pending
        else DailyFeatureOutcomeObservationRunStatus.COMPLETED
    )
