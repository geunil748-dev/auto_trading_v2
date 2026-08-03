"""Aggregate invariants and content digest for observation run audits."""

from dataclasses import dataclass, field

from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)
from auto_trading_v2.domain.feature_outcomes.identity import outcome_content_digest
from auto_trading_v2.domain.feature_outcomes.observation import (
    DailyFeatureOutcomeObservationRun,
    DailyFeatureOutcomeObservationRunItem,
)
from auto_trading_v2.domain.feature_outcomes.outcomes import (
    DailyFeatureOutcomeObservationRunItemOutcome,
)


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeObservationRunWithItems:
    run: DailyFeatureOutcomeObservationRun
    items: tuple[DailyFeatureOutcomeObservationRunItem, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.items) != self.run.total_count:
            _invalid("OBSERVATION_RUN_ITEM_TOTAL_MISMATCH")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            _invalid("OBSERVATION_RUN_ITEM_ORDER_INVALID")
        if any(
            item.daily_feature_outcome_observation_run_id
            != self.run.daily_feature_outcome_observation_run_id
            for item in self.items
        ):
            _invalid("OBSERVATION_RUN_ITEM_RUN_MISMATCH")
        if len({item.source_daily_feature_scoring_item_id for item in self.items}) != len(
            self.items
        ):
            _invalid("OBSERVATION_RUN_SOURCE_ITEM_DUPLICATE")
        expected = _counts(self.items)
        if self.run.counts != expected:
            _invalid("OBSERVATION_RUN_ITEM_COUNT_MISMATCH")
        if self.run.content_digest != daily_feature_outcome_observation_content_digest(
            self.run, self.items
        ):
            _invalid("OBSERVATION_RUN_DIGEST_MISMATCH")


def daily_feature_outcome_observation_content_digest(
    run: DailyFeatureOutcomeObservationRun,
    items: tuple[DailyFeatureOutcomeObservationRunItem, ...],
) -> str:
    payload = {
        "counts": {
            "incomplete": run.incomplete_count,
            "ineligible": run.ineligible_count,
            "invalid": run.invalid_count,
            "not_matured": run.not_matured_count,
            "outcome_created": run.outcome_created_count,
            "outcome_existing": run.outcome_existing_count,
            "total": run.total_count,
        },
        "items": [item.digest_payload() for item in items],
        "status": run.status.value,
    }
    return outcome_content_digest(payload)


def _counts(
    items: tuple[DailyFeatureOutcomeObservationRunItem, ...],
) -> tuple[int, ...]:
    outcomes = tuple(item.outcome for item in items)
    return (
        outcomes.count(DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_CREATED),
        outcomes.count(DailyFeatureOutcomeObservationRunItemOutcome.OUTCOME_ALREADY_EXISTS),
        outcomes.count(DailyFeatureOutcomeObservationRunItemOutcome.NOT_MATURED),
        outcomes.count(DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BARS_INCOMPLETE),
        outcomes.count(DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_ITEM_NOT_ELIGIBLE),
        sum(
            outcome
            in {
                DailyFeatureOutcomeObservationRunItemOutcome.SOURCE_CHAIN_INVALID,
                DailyFeatureOutcomeObservationRunItemOutcome.FUTURE_BAR_CONTRACT_INVALID,
                DailyFeatureOutcomeObservationRunItemOutcome.CALENDAR_OUT_OF_COVERAGE,
            }
            for outcome in outcomes
        ),
    )


def _invalid(category: str) -> None:
    raise OutcomeObservationValidationError(category)
