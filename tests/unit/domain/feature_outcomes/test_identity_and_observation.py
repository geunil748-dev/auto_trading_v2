from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.feature_outcomes import (
    ObserveDailyFeatureScoringOutcomesCommand,
)
from auto_trading_v2.application.services.daily_feature_outcome_run_builder import (
    ObservationRunItemSource,
    build_observation_run,
)
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcomeIdentity,
    DailyFeatureOutcomeObservationRunItemOutcome,
    DailyFeatureOutcomeObservationRunStatus,
    OutcomeObservationRunIdentity,
    calculate_forward_outcome,
    daily_feature_outcome_key,
    daily_feature_outcome_observation_run_key,
    fixed_outcome_policy_values,
    path_revision_digest,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.market_calendar import CompletionGracePeriod
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeObservationRunID,
    DailyFeatureOutcomeObservationRunItemID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
)

from .helpers import OBSERVATION_AS_OF, SYMBOL, expected_sessions, outcome_bar


@dataclass
class RunIDs:
    value: int = 700

    def new(self) -> DailyFeatureOutcomeObservationRunID:
        return DailyFeatureOutcomeObservationRunID(UUID(int=self.value))


@dataclass
class ItemIDs:
    value: int = 800

    def new(self) -> DailyFeatureOutcomeObservationRunItemID:
        self.value += 1
        return DailyFeatureOutcomeObservationRunItemID(UUID(int=self.value))


def test_path_revision_digest_and_outcome_key_are_revision_sensitive() -> None:
    bars = (outcome_bar(1, close="101"), outcome_bar(2, close="102"))
    first = calculate_forward_outcome(
        Decimal("100"),
        bars,
        expected_sessions(bars),
        SYMBOL,
        OBSERVATION_AS_OF,
    )
    corrected_bars = (
        bars[0],
        outcome_bar(2, close="103", source_version="v2-corrected"),
    )
    corrected = calculate_forward_outcome(
        Decimal("100"),
        corrected_bars,
        expected_sessions(corrected_bars),
        SYMBOL,
        OBSERVATION_AS_OF,
    )
    code, version = fixed_outcome_policy_values()
    source_id = DailyFeatureScoringItemID(UUID(int=1))
    first_identity = DailyFeatureOutcomeIdentity(
        source_id,
        code,
        version,
        TradingDayHorizon(2),
        path_revision_digest(first.future_bar_provenance),
    )
    same_identity = DailyFeatureOutcomeIdentity(
        source_id,
        code,
        version,
        TradingDayHorizon(2),
        path_revision_digest(first.future_bar_provenance),
    )
    corrected_identity = DailyFeatureOutcomeIdentity(
        source_id,
        code,
        version,
        TradingDayHorizon(2),
        path_revision_digest(corrected.future_bar_provenance),
    )

    assert daily_feature_outcome_key(first_identity) == daily_feature_outcome_key(same_identity)
    assert daily_feature_outcome_key(first_identity) != daily_feature_outcome_key(
        corrected_identity
    )


@pytest.mark.parametrize(
    ("outcomes", "status"),
    [
        (
            (DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED,),
            DailyFeatureOutcomeObservationRunStatus.COMPLETED,
        ),
        (
            (DailyFeatureOutcomeObservationRunItemOutcome.NOT_MATURED,),
            DailyFeatureOutcomeObservationRunStatus.COMPLETED_WITH_PENDING,
        ),
        (
            (DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_CHAIN_INVALID,),
            DailyFeatureOutcomeObservationRunStatus.COMPLETED_WITH_GAPS,
        ),
        (
            (DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_ITEM_NOT_ELIGIBLE,),
            DailyFeatureOutcomeObservationRunStatus.NO_ELIGIBLE_ITEMS,
        ),
        (
            (DailyFeatureOutcomeObservationRunItemOutcome.CALENDAR_OUT_OF_COVERAGE,),
            DailyFeatureOutcomeObservationRunStatus.CALENDAR_OUT_OF_COVERAGE,
        ),
    ],
)
def test_observation_run_status_and_digest_shape(
    outcomes: tuple[DailyFeatureOutcomeObservationRunItemOutcome, ...],
    status: DailyFeatureOutcomeObservationRunStatus,
) -> None:
    scoring_run_id = DailyFeatureScoringRunID(UUID(int=2))
    code, version = fixed_outcome_policy_values()
    identity = OutcomeObservationRunIdentity(
        scoring_run_id,
        code,
        version,
        OBSERVATION_AS_OF,
        900,
    )
    sources = tuple(
        ObservationRunItemSource(
            DailyFeatureScoringItemID(UUID(int=index)),
            outcome,
            DailyFeatureOutcomeID(UUID(int=100 + index))
            if outcome is DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED
            else None,
            expected_sessions((outcome_bar(index, close="101"),))[0]
            if outcome is DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED
            else None,
        )
        for index, outcome in enumerate(outcomes, 1)
    )

    aggregate = build_observation_run(
        identity,
        daily_feature_outcome_observation_run_key(identity),
        sources,
        OBSERVATION_AS_OF + timedelta(seconds=1),
        RunIDs(),
        ItemIDs(),
    )

    assert aggregate.run.status is status
    assert aggregate.run.total_count == len(outcomes)
    assert len(aggregate.run.content_digest) == 64


def test_command_accepts_only_utc_fixed_policy_and_whole_second_grace() -> None:
    run_id = DailyFeatureScoringRunID(UUID(int=3))
    command = ObserveDailyFeatureScoringOutcomesCommand(
        run_id,
        OBSERVATION_AS_OF,
        CompletionGracePeriod(timedelta(minutes=15)),
    )
    assert command.observation_as_of.tzinfo is UTC

    with pytest.raises(ValueError, match="timezone-aware"):
        ObserveDailyFeatureScoringOutcomesCommand(
            run_id,
            datetime(2026, 8, 1),
            CompletionGracePeriod(timedelta()),
        )
    with pytest.raises(ValueError, match="unsupported"):
        ObserveDailyFeatureScoringOutcomesCommand(
            run_id,
            OBSERVATION_AS_OF,
            CompletionGracePeriod(timedelta()),
            outcome_policy_version="v2",
        )
