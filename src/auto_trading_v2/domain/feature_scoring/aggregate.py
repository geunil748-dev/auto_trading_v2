"""Aggregate-level ordering and digest invariants for P4A scoring."""

from dataclasses import dataclass, field
from decimal import Decimal

from auto_trading_v2.domain.feature_scoring.errors import FeatureScoringValidationError
from auto_trading_v2.domain.feature_scoring.identity import feature_scoring_content_digest
from auto_trading_v2.domain.feature_scoring.models import (
    DailyFeatureScoringItem,
    DailyFeatureScoringRun,
    RelativeScore,
)
from auto_trading_v2.domain.feature_scoring.outcomes import DailyFeatureScoringItemOutcome

_SCORED = frozenset(
    {
        DailyFeatureScoringItemOutcome.SCORED_READY,
        DailyFeatureScoringItemOutcome.SCORED_DEGRADED,
    }
)


@dataclass(frozen=True, slots=True)
class DailyFeatureScoringRunWithItems:
    run: DailyFeatureScoringRun
    items: tuple[DailyFeatureScoringItem, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.items) != self.run.total_count:
            _invalid("SCORING_ITEM_TOTAL_MISMATCH")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            _invalid("SCORING_ITEM_ORDER_INVALID")
        if any(
            item.daily_feature_scoring_run_id != self.run.daily_feature_scoring_run_id
            for item in self.items
        ):
            _invalid("SCORING_ITEM_RUN_MISMATCH")
        if len({item.source_daily_feature_pipeline_item_id for item in self.items}) != len(
            self.items
        ):
            _invalid("SCORING_SOURCE_ITEM_DUPLICATE")
        if len({item.symbol for item in self.items}) != len(self.items):
            _invalid("SCORING_ITEM_SYMBOL_DUPLICATE")
        ranked = tuple(item for item in self.items if item.outcome in _SCORED)
        if sorted(item.rank or 0 for item in ranked) != list(range(1, len(ranked) + 1)):
            _invalid("SCORING_RANK_SEQUENCE_INVALID")
        expected = sorted(ranked, key=_rank_key)
        persisted_order = sorted(ranked, key=lambda item: item.rank or 0)
        if [item.daily_feature_scoring_item_id for item in expected] != [
            item.daily_feature_scoring_item_id for item in persisted_order
        ]:
            _invalid("SCORING_RANK_POLICY_INVALID")
        if self.run.content_digest != daily_feature_scoring_content_digest(self.run, self.items):
            _invalid("SCORING_CONTENT_DIGEST_MISMATCH")


def daily_feature_scoring_content_digest(
    run: DailyFeatureScoringRun,
    items: tuple[DailyFeatureScoringItem, ...],
) -> str:
    return feature_scoring_content_digest(
        {
            "counts": {
                "scored_degraded": run.scored_degraded_count,
                "scored_ready": run.scored_ready_count,
                "total": run.total_count,
                "unscorable": run.unscorable_count,
            },
            "items": [item.digest_payload() for item in items],
            "status": run.status.value,
        }
    )


def _rank_key(item: DailyFeatureScoringItem) -> tuple[object, ...]:
    zero = RelativeScore(Decimal(0))
    return (
        0 if item.outcome is DailyFeatureScoringItemOutcome.SCORED_READY else 1,
        -(item.overall_relative_score or zero).value,
        -(item.momentum_score or zero).value,
        -(item.trend_score or zero).value,
        item.mic_code,
        item.symbol.value,
    )


def _invalid(category: str) -> None:
    raise FeatureScoringValidationError(category)
