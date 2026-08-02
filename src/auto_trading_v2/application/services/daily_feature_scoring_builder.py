"""Pure preparation of P3 items into P4A scored and audited item records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from auto_trading_v2.application.contracts.feature_scoring import NewDailyFeatureScoringItem
from auto_trading_v2.application.ports.id_factory import DailyFeatureScoringItemIDFactory
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItem,
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRun,
)
from auto_trading_v2.domain.feature_scoring import (
    CalculatedComponentScores,
    DailyFeatureScoringItemOutcome,
    FeatureScoringValidationError,
    RankingInput,
    RelativeScore,
    ValidatedTechnicalFeatures,
    calculate_component_scores,
    deterministic_ranks,
    parse_v1_technical_features,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, FeatureSnapshot
from auto_trading_v2.domain.primitives import (
    DailyFeaturePipelineItemID,
    DailyFeatureScoringRunID,
)


@dataclass(frozen=True, slots=True)
class PreparedFeatureScoringItem:
    source: DailyFeaturePipelineItem
    snapshot: FeatureSnapshot | None
    features: ValidatedTechnicalFeatures | None
    outcome: DailyFeatureScoringItemOutcome | None
    safe_reason_code: str | None


def prepare_scoring_item(
    source_run: DailyFeaturePipelineRun,
    item: DailyFeaturePipelineItem,
    snapshot: FeatureSnapshot | None,
) -> PreparedFeatureScoringItem:
    if item.outcome not in {
        DailyFeaturePipelineItemOutcome.READY,
        DailyFeaturePipelineItemOutcome.DEGRADED,
    }:
        return PreparedFeatureScoringItem(
            item,
            None,
            None,
            DailyFeatureScoringItemOutcome.SOURCE_ITEM_NOT_SCORABLE,
            f"SOURCE_ITEM_{item.outcome.value}",
        )
    if snapshot is None:
        return PreparedFeatureScoringItem(
            item,
            None,
            None,
            DailyFeatureScoringItemOutcome.FEATURE_SNAPSHOT_MISSING,
            "FEATURE_SNAPSHOT_MISSING",
        )
    source = snapshot.snapshot_input
    if (
        snapshot.feature_snapshot_id != item.feature_snapshot_id
        or source.symbol != item.symbol
        or source.horizon != source_run.identity.horizon
        or source.as_of != source_run.identity.as_of
        or source.quality_status is not item.feature_quality_status
        or any(
            entry.source_code != source_run.identity.provider_code for entry in source.provenance
        )
    ):
        return PreparedFeatureScoringItem(
            item,
            snapshot,
            None,
            DailyFeatureScoringItemOutcome.FEATURE_SOURCE_MISMATCH,
            "FEATURE_SOURCE_MISMATCH",
        )
    try:
        features = parse_v1_technical_features(snapshot)
    except FeatureScoringValidationError as exc:
        quality = exc.category == "FEATURE_QUALITY_UNSUPPORTED"
        return PreparedFeatureScoringItem(
            item,
            snapshot,
            None,
            (
                DailyFeatureScoringItemOutcome.FEATURE_QUALITY_UNSUPPORTED
                if quality
                else DailyFeatureScoringItemOutcome.FEATURE_CONTRACT_INVALID
            ),
            exc.category,
        )
    return PreparedFeatureScoringItem(item, snapshot, features, None, None)


def build_scoring_items(
    run_id: DailyFeatureScoringRunID,
    prepared: tuple[PreparedFeatureScoringItem, ...],
    generated_at: datetime,
    id_factory: DailyFeatureScoringItemIDFactory,
) -> tuple[NewDailyFeatureScoringItem, ...]:
    candidates: dict[DailyFeaturePipelineItemID, ValidatedTechnicalFeatures] = {}
    qualities: dict[DailyFeaturePipelineItemID, FeatureQualityStatus] = {}
    for entry in prepared:
        if entry.features is not None and entry.snapshot is not None:
            key = entry.source.daily_feature_pipeline_item_id
            candidates[key] = entry.features
            qualities[key] = entry.snapshot.snapshot_input.quality_status
    calculated = calculate_component_scores(candidates, qualities)
    persisted = {key: _persisted_scores(scores) for key, scores in calculated.items()}
    ranks = deterministic_ranks(
        tuple(
            RankingInput(
                key,
                qualities[key],
                entry.source.mic_code,
                entry.source.symbol,
                scores,
            )
            for entry in prepared
            if (key := entry.source.daily_feature_pipeline_item_id) in persisted
            for scores in (persisted[key],)
        )
    )
    return tuple(
        _new_item(run_id, entry, persisted, ranks, generated_at, id_factory) for entry in prepared
    )


def _new_item(
    run_id: DailyFeatureScoringRunID,
    prepared: PreparedFeatureScoringItem,
    calculated: dict[DailyFeaturePipelineItemID, CalculatedComponentScores],
    ranks: dict[object, int],
    generated_at: datetime,
    id_factory: DailyFeatureScoringItemIDFactory,
) -> NewDailyFeatureScoringItem:
    source = prepared.source
    scores = calculated.get(source.daily_feature_pipeline_item_id)
    quality = source.feature_quality_status
    outcome = prepared.outcome
    reason = prepared.safe_reason_code
    if scores is not None:
        outcome = (
            DailyFeatureScoringItemOutcome.SCORED_READY
            if quality is FeatureQualityStatus.READY
            else DailyFeatureScoringItemOutcome.SCORED_DEGRADED
        )
        reason = (
            None
            if outcome is DailyFeatureScoringItemOutcome.SCORED_READY
            else prepared.snapshot.snapshot_input.quality_reason_codes[0]  # type: ignore[union-attr]
        )
    if outcome is None:
        raise RuntimeError("prepared scoring outcome is inconsistent")
    return NewDailyFeatureScoringItem(
        id_factory.new(),
        run_id,
        source.daily_feature_pipeline_item_id,
        source.ordinal,
        None if scores is None else ranks[source.daily_feature_pipeline_item_id],
        source.symbol,
        source.mic_code,
        None if prepared.snapshot is None else prepared.snapshot.feature_snapshot_id,
        quality,
        outcome,
        _relative(scores.momentum if scores else None),
        _relative(scores.trend if scores else None),
        _relative(scores.breakout if scores else None),
        _relative(scores.price_action if scores else None),
        _relative(scores.stability if scores else None),
        _relative(scores.volume if scores else None),
        _relative(scores.overall if scores else None),
        reason,
        generated_at,
    )


def _relative(value: Decimal | None) -> RelativeScore | None:
    return None if value is None else RelativeScore(value)


def _persisted_scores(scores: CalculatedComponentScores) -> CalculatedComponentScores:
    def fixed(value: Decimal) -> Decimal:
        return RelativeScore(value).value

    return CalculatedComponentScores(
        fixed(scores.momentum),
        fixed(scores.trend),
        fixed(scores.breakout),
        fixed(scores.price_action),
        fixed(scores.stability),
        None if scores.volume is None else fixed(scores.volume),
        fixed(scores.overall),
    )
