"""Provider-neutral read-only lineage query for one persisted P4B.2A dataset."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, case, exists, select

from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_outcome_labels,
    daily_feature_outcomes,
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
    feature_snapshots,
)
from auto_trading_v2.application.contracts.training_readiness import (
    TrainingReadinessLineageRecord,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.calibration_datasets import ProbabilityCalibrationDataset
from auto_trading_v2.domain.primitives import DailyFeatureScoringItemID, Symbol


def training_readiness_lineage_statement(
    dataset: ProbabilityCalibrationDataset,
) -> Select[Any]:
    identity = dataset.identity
    scoring_item = daily_feature_scoring_items
    scoring_run = daily_feature_scoring_runs
    pipeline_item = daily_feature_pipeline_items
    pipeline_run = daily_feature_pipeline_runs
    snapshot = feature_snapshots
    outcome = daily_feature_outcomes
    label = daily_feature_outcome_labels
    base_outcome = (
        outcome.c.source_daily_feature_scoring_item_id
        == scoring_item.c.daily_feature_scoring_item_id,
        outcome.c.horizon_trading_days == identity.horizon.value,
    )
    as_of_outcome = (
        *base_outcome,
        outcome.c.latest_input_available_at <= identity.dataset_as_of,
        outcome.c.recorded_at <= identity.dataset_as_of,
    )
    provider_outcome = (*as_of_outcome, outcome.c.provider_code == identity.provider_code)
    calendar_outcome = (
        *provider_outcome,
        outcome.c.calendar_code == identity.calendar_code.value,
        outcome.c.calendar_version == identity.calendar_version.value,
    )
    policy_outcome = (
        *calendar_outcome,
        outcome.c.outcome_policy_code == identity.outcome_policy_code.value,
        outcome.c.outcome_policy_version == identity.outcome_policy_version.value,
    )
    label_source = label.join(
        outcome,
        label.c.source_daily_feature_outcome_id == outcome.c.daily_feature_outcome_id,
    )
    any_label = (
        *policy_outcome,
        label.c.source_daily_feature_scoring_item_id
        == scoring_item.c.daily_feature_scoring_item_id,
    )
    matching_label = (
        *any_label,
        label.c.label_policy_code == identity.label_policy_code.value,
        label.c.label_policy_version == identity.label_policy_version.value,
    )
    return (
        select(
            scoring_item.c.daily_feature_scoring_item_id,
            scoring_item.c.symbol,
            scoring_item.c.mic_code,
            pipeline_item.c.completed_session_date.label("source_session_date"),
            pipeline_run.c.provider_code,
            pipeline_run.c.calendar_code,
            pipeline_run.c.calendar_version,
            scoring_run.c.scoring_policy_code,
            scoring_run.c.scoring_policy_version,
            scoring_run.c.ranking_policy_code,
            scoring_run.c.ranking_policy_version,
            scoring_item.c.outcome.label("scoring_outcome"),
            scoring_item.c.source_quality_status,
            pipeline_item.c.outcome.label("pipeline_outcome"),
            snapshot.c.quality_status.label("feature_quality_status"),
            snapshot.c.quality_reason_codes,
            scoring_item.c.overall_relative_score,
            scoring_item.c.rank.label("source_rank"),
            _flag(base_outcome).label("has_any_outcome"),
            _flag(as_of_outcome).label("has_as_of_outcome"),
            _flag(provider_outcome).label("has_provider_outcome"),
            _flag(calendar_outcome).label("has_calendar_outcome"),
            _flag(policy_outcome).label("has_policy_outcome"),
            _flag(any_label, label_source).label("has_any_label"),
            _flag(matching_label, label_source).label("has_matching_label"),
        )
        .select_from(
            scoring_item.join(
                scoring_run,
                scoring_item.c.daily_feature_scoring_run_id
                == scoring_run.c.daily_feature_scoring_run_id,
            )
            .join(
                pipeline_item,
                scoring_item.c.source_daily_feature_pipeline_item_id
                == pipeline_item.c.daily_feature_pipeline_item_id,
            )
            .join(
                pipeline_run,
                scoring_run.c.source_daily_feature_pipeline_run_id
                == pipeline_run.c.daily_feature_pipeline_run_id,
            )
            .outerjoin(
                snapshot,
                scoring_item.c.feature_snapshot_id == snapshot.c.feature_snapshot_id,
            )
        )
        .where(
            pipeline_item.c.daily_feature_pipeline_run_id
            == pipeline_run.c.daily_feature_pipeline_run_id,
            pipeline_run.c.horizon_trading_days == identity.horizon.value,
            scoring_run.c.generated_at <= identity.dataset_as_of,
            scoring_item.c.recorded_at <= identity.dataset_as_of,
        )
        .order_by(
            pipeline_item.c.completed_session_date.asc(),
            scoring_run.c.daily_feature_scoring_run_id.asc(),
            scoring_item.c.ordinal.asc(),
            scoring_item.c.daily_feature_scoring_item_id.asc(),
        )
    )


def map_training_readiness_lineage_record(
    row: Mapping[Any, Any],
) -> TrainingReadinessLineageRecord:
    try:
        session = row["source_session_date"]
        return TrainingReadinessLineageRecord(
            source_daily_feature_scoring_item_id=DailyFeatureScoringItemID(
                _uuid(row["daily_feature_scoring_item_id"])
            ),
            symbol=Symbol(_string(row["symbol"])),
            mic_code=_string(row["mic_code"]),
            source_session_date=None if session is None else _date(session),
            provider_code=_string(row["provider_code"]),
            calendar_code=_string(row["calendar_code"]),
            calendar_version=_string(row["calendar_version"]),
            scoring_policy_code=_string(row["scoring_policy_code"]),
            scoring_policy_version=_string(row["scoring_policy_version"]),
            ranking_policy_code=_string(row["ranking_policy_code"]),
            ranking_policy_version=_string(row["ranking_policy_version"]),
            scoring_outcome=_string(row["scoring_outcome"]),
            source_quality_status=_optional_string(row["source_quality_status"]),
            pipeline_outcome=_string(row["pipeline_outcome"]),
            feature_quality_status=_optional_string(row["feature_quality_status"]),
            quality_reason_codes=_quality_reasons(row["quality_reason_codes"]),
            overall_relative_score=_optional_decimal(row["overall_relative_score"]),
            source_rank=_optional_int(row["source_rank"]),
            has_any_outcome=_boolean(row["has_any_outcome"]),
            has_as_of_outcome=_boolean(row["has_as_of_outcome"]),
            has_provider_outcome=_boolean(row["has_provider_outcome"]),
            has_calendar_outcome=_boolean(row["has_calendar_outcome"]),
            has_policy_outcome=_boolean(row["has_policy_outcome"]),
            has_any_label=_boolean(row["has_any_label"]),
            has_matching_label=_boolean(row["has_matching_label"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise PersistenceMappingError("training_readiness_lineage") from None


def _flag(criteria: tuple[Any, ...], source: Any | None = None) -> Any:
    statement = select(1)
    if source is not None:
        statement = statement.select_from(source)
    return case((exists(statement.where(*criteria)), 1), else_=0)


def _quality_reasons(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    decoded = json.loads(_string(value))
    if not isinstance(decoded, list) or any(not isinstance(item, str) for item in decoded):
        raise TypeError
    return tuple(decoded)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value


def _optional_string(value: object) -> str | None:
    return None if value is None else _string(value)


def _date(value: object) -> date:
    if not isinstance(value, date):
        raise TypeError
    return value


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _boolean(value: object) -> bool:
    if value not in (0, 1, False, True):
        raise TypeError
    return bool(value)
