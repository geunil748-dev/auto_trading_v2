"""Immutable P4A relative-scoring aggregate and fixed Decimal values."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, localcontext

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_scoring.errors import FeatureScoringValidationError
from auto_trading_v2.domain.feature_scoring.identity import (
    DailyFeatureScoringIdentity,
    daily_feature_scoring_run_key,
)
from auto_trading_v2.domain.feature_scoring.outcomes import (
    DailyFeatureScoringItemOutcome,
    DailyFeatureScoringRunStatus,
)
from auto_trading_v2.domain.feature_scoring.scoring import DECIMAL_CONTEXT
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    FeatureSnapshotID,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

_RUN_KEY = re.compile(r"^daily-feature-scoring-run:v1:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,95}$")
_SCORE_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class RelativeScore:
    """A fixed-scale 0..100 relative score; never a probability."""

    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            _invalid("RELATIVE_SCORE_INVALID")
        if self.value < 0 or self.value > 100:
            _invalid("RELATIVE_SCORE_OUT_OF_RANGE")
        with localcontext(DECIMAL_CONTEXT):
            normalized = self.value.quantize(_SCORE_QUANTUM)
        object.__setattr__(self, "value", normalized)

    def serialize(self) -> str:
        return format(self.value, ".6f")


@dataclass(frozen=True, slots=True)
class DailyFeatureScoringItem:
    daily_feature_scoring_item_id: DailyFeatureScoringItemID
    daily_feature_scoring_run_id: DailyFeatureScoringRunID
    source_daily_feature_pipeline_item_id: DailyFeaturePipelineItemID
    ordinal: int
    rank: int | None
    symbol: Symbol
    mic_code: str
    feature_snapshot_id: FeatureSnapshotID | None
    source_quality_status: FeatureQualityStatus | None
    outcome: DailyFeatureScoringItemOutcome
    momentum_score: RelativeScore | None
    trend_score: RelativeScore | None
    breakout_score: RelativeScore | None
    price_action_score: RelativeScore | None
    stability_score: RelativeScore | None
    volume_score: RelativeScore | None
    overall_relative_score: RelativeScore | None
    safe_reason_code: str | None
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.daily_feature_scoring_item_id, DailyFeatureScoringItemID):
            _invalid("SCORING_ITEM_ID_INVALID")
        if not isinstance(self.daily_feature_scoring_run_id, DailyFeatureScoringRunID):
            _invalid("SCORING_RUN_ID_INVALID")
        if not isinstance(self.source_daily_feature_pipeline_item_id, DailyFeaturePipelineItemID):
            _invalid("SCORING_SOURCE_ITEM_ID_INVALID")
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or not 1 <= self.ordinal <= 100
        ):
            _invalid("SCORING_ITEM_ORDINAL_INVALID")
        if self.rank is not None and (
            isinstance(self.rank, bool)
            or not isinstance(self.rank, int)
            or not 1 <= self.rank <= 100
        ):
            _invalid("SCORING_ITEM_RANK_INVALID")
        if not isinstance(self.symbol, Symbol):
            _invalid("SCORING_ITEM_SYMBOL_INVALID")
        if self.mic_code not in {"XNGS", "XNGM", "XNCM", "XNYS", "XASE"}:
            _invalid("SCORING_ITEM_MIC_INVALID")
        if not isinstance(self.outcome, DailyFeatureScoringItemOutcome):
            _invalid("SCORING_ITEM_OUTCOME_INVALID")
        if self.source_quality_status is not None and not isinstance(
            self.source_quality_status, FeatureQualityStatus
        ):
            _invalid("SCORING_ITEM_QUALITY_INVALID")
        if self.safe_reason_code is not None and not _REASON.fullmatch(self.safe_reason_code):
            _invalid("SCORING_ITEM_REASON_INVALID")
        scores = self.component_scores
        if self.outcome is DailyFeatureScoringItemOutcome.SCORED_READY:
            if (
                self.feature_snapshot_id is None
                or self.source_quality_status is not FeatureQualityStatus.READY
                or self.rank is None
                or any(score is None for score in scores)
                or self.overall_relative_score is None
            ):
                _invalid("SCORING_READY_SHAPE_INVALID")
        elif self.outcome is DailyFeatureScoringItemOutcome.SCORED_DEGRADED:
            if (
                self.feature_snapshot_id is None
                or self.source_quality_status is not FeatureQualityStatus.DEGRADED
                or self.rank is None
                or any(score is None for score in scores[:-1])
                or self.volume_score is not None
                or self.overall_relative_score is None
            ):
                _invalid("SCORING_DEGRADED_SHAPE_INVALID")
        elif (
            self.rank is not None
            or any(score is not None for score in scores)
            or self.overall_relative_score is not None
            or self.safe_reason_code is None
        ):
            _invalid("SCORING_UNSCORABLE_SHAPE_INVALID")
        generated = _timestamp(self.generated_at, "SCORING_ITEM_GENERATED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "SCORING_ITEM_RECORDED_AT_INVALID")
        if generated > recorded:
            _invalid("SCORING_ITEM_TIME_ORDER_INVALID")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)

    @property
    def component_scores(self) -> tuple[RelativeScore | None, ...]:
        return (
            self.momentum_score,
            self.trend_score,
            self.breakout_score,
            self.price_action_score,
            self.stability_score,
            self.volume_score,
        )

    def digest_payload(self) -> dict[str, object]:
        return {
            "breakout_score": _score(self.breakout_score),
            "feature_snapshot_id": _identifier(self.feature_snapshot_id),
            "mic_code": self.mic_code,
            "momentum_score": _score(self.momentum_score),
            "ordinal": self.ordinal,
            "outcome": self.outcome.value,
            "overall_relative_score": _score(self.overall_relative_score),
            "price_action_score": _score(self.price_action_score),
            "rank": self.rank,
            "safe_reason_code": self.safe_reason_code,
            "source_daily_feature_pipeline_item_id": (
                self.source_daily_feature_pipeline_item_id.serialize()
            ),
            "source_quality_status": (
                None if self.source_quality_status is None else self.source_quality_status.value
            ),
            "stability_score": _score(self.stability_score),
            "symbol": self.symbol.serialize(),
            "trend_score": _score(self.trend_score),
            "volume_score": _score(self.volume_score),
        }


@dataclass(frozen=True, slots=True)
class DailyFeatureScoringRun:
    daily_feature_scoring_run_id: DailyFeatureScoringRunID
    scoring_run_key: str
    content_digest: str
    identity: DailyFeatureScoringIdentity = field(repr=False)
    status: DailyFeatureScoringRunStatus
    total_count: int
    scored_ready_count: int
    scored_degraded_count: int
    unscorable_count: int
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.daily_feature_scoring_run_id, DailyFeatureScoringRunID):
            _invalid("SCORING_RUN_ID_INVALID")
        if not _RUN_KEY.fullmatch(
            self.scoring_run_key
        ) or self.scoring_run_key != daily_feature_scoring_run_key(self.identity):
            _invalid("SCORING_RUN_KEY_INVALID")
        if not _DIGEST.fullmatch(self.content_digest):
            _invalid("SCORING_CONTENT_DIGEST_INVALID")
        if not isinstance(self.status, DailyFeatureScoringRunStatus):
            _invalid("SCORING_RUN_STATUS_INVALID")
        counts = (
            self.total_count,
            self.scored_ready_count,
            self.scored_degraded_count,
            self.unscorable_count,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100
            for value in counts
        ):
            _invalid("SCORING_RUN_COUNT_INVALID")
        if self.total_count != sum(counts[1:]):
            _invalid("SCORING_RUN_COUNT_SUM_INVALID")
        scored = self.scored_ready_count + self.scored_degraded_count
        if self.status is DailyFeatureScoringRunStatus.COMPLETED and self.unscorable_count != 0:
            _invalid("SCORING_RUN_STATUS_SHAPE_INVALID")
        if self.status is DailyFeatureScoringRunStatus.COMPLETED_WITH_UNSCORABLE and not (
            scored > 0 and self.unscorable_count > 0
        ):
            _invalid("SCORING_RUN_STATUS_SHAPE_INVALID")
        if self.status is DailyFeatureScoringRunStatus.NO_SCORABLE_ITEMS and scored != 0:
            _invalid("SCORING_RUN_STATUS_SHAPE_INVALID")
        generated = _timestamp(self.generated_at, "SCORING_RUN_GENERATED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "SCORING_RUN_RECORDED_AT_INVALID")
        if generated > recorded:
            _invalid("SCORING_RUN_TIME_ORDER_INVALID")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)


def _score(value: RelativeScore | None) -> str | None:
    return None if value is None else value.serialize()


def _identifier(value: FeatureSnapshotID | None) -> str | None:
    return None if value is None else value.serialize()


def _timestamp(value: object, category: str) -> datetime:
    try:
        return normalize_utc(value)  # type: ignore[arg-type]
    except (TypeError, ValidationError):
        raise FeatureScoringValidationError(category) from None


def _invalid(category: str) -> None:
    raise FeatureScoringValidationError(category)
