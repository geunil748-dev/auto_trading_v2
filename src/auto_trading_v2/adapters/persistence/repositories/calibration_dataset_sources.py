"""One-query Point-in-Time source selection for P4B.2A datasets."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, Select, func, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.tables import (
    daily_feature_outcomes,
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.calibration_datasets import (
    DATASET_POLICY_CODE,
    DATASET_POLICY_VERSION,
    CalibrationDatasetPolicyCode,
    CalibrationDatasetPolicyVersion,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    SOURCE_PROVIDER_CODE,
)
from auto_trading_v2.domain.feature_scoring import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives.time import normalize_utc

from .calibration_dataset_source_mapping import map_calibration_dataset_source

_SOURCE_COLUMNS = (
    "source_daily_feature_scoring_run_id",
    "source_daily_feature_scoring_item_id",
    "source_daily_feature_pipeline_run_id",
    "source_daily_feature_pipeline_item_id",
    "feature_snapshot_id",
    "source_daily_feature_outcome_id",
    "source_outcome_key",
    "source_outcome_content_digest",
    "source_path_revision_digest",
    "symbol",
    "mic_code",
    "horizon_trading_days",
    "source_session_date",
    "terminal_session_date",
    "source_scoring_generated_at",
    "source_scoring_item_recorded_at",
    "outcome_latest_input_available_at",
    "outcome_recorded_at",
    "observation_mode",
    "source_quality_status",
    "overall_relative_score",
    "source_rank",
    "forward_close_return",
    "provider_code",
    "calendar_code",
    "calendar_version",
    "outcome_policy_code",
    "outcome_policy_version",
    "scoring_policy_code",
    "scoring_policy_version",
    "ranking_policy_code",
    "ranking_policy_version",
)


def eligible_calibration_dataset_sources_statement(
    horizon: TradingDayHorizon,
    dataset_as_of: datetime,
) -> Select[Any]:
    outcome = daily_feature_outcomes
    item = daily_feature_scoring_items
    run = daily_feature_scoring_runs
    ranked = (
        select(
            outcome.c.source_daily_feature_scoring_run_id,
            outcome.c.source_daily_feature_scoring_item_id,
            outcome.c.source_daily_feature_pipeline_run_id,
            outcome.c.source_daily_feature_pipeline_item_id,
            outcome.c.feature_snapshot_id,
            outcome.c.daily_feature_outcome_id.label("source_daily_feature_outcome_id"),
            outcome.c.outcome_key.label("source_outcome_key"),
            outcome.c.content_digest.label("source_outcome_content_digest"),
            outcome.c.path_revision_digest.label("source_path_revision_digest"),
            outcome.c.symbol,
            outcome.c.mic_code,
            outcome.c.horizon_trading_days,
            outcome.c.source_session_date,
            outcome.c.terminal_session_date,
            run.c.generated_at.label("source_scoring_generated_at"),
            item.c.recorded_at.label("source_scoring_item_recorded_at"),
            outcome.c.latest_input_available_at.label("outcome_latest_input_available_at"),
            outcome.c.recorded_at.label("outcome_recorded_at"),
            outcome.c.observation_mode,
            item.c.source_quality_status,
            item.c.overall_relative_score,
            item.c.rank.label("source_rank"),
            outcome.c.forward_close_return,
            outcome.c.provider_code,
            outcome.c.calendar_code,
            outcome.c.calendar_version,
            outcome.c.outcome_policy_code,
            outcome.c.outcome_policy_version,
            run.c.scoring_policy_code,
            run.c.scoring_policy_version,
            run.c.ranking_policy_code,
            run.c.ranking_policy_version,
            func.row_number()
            .over(
                partition_by=outcome.c.source_daily_feature_scoring_item_id,
                order_by=(
                    outcome.c.latest_input_available_at.desc(),
                    outcome.c.recorded_at.desc(),
                    outcome.c.outcome_key.desc(),
                ),
            )
            .label("revision_rank"),
        )
        .select_from(
            outcome.join(
                item,
                outcome.c.source_daily_feature_scoring_item_id
                == item.c.daily_feature_scoring_item_id,
            ).join(
                run,
                outcome.c.source_daily_feature_scoring_run_id == run.c.daily_feature_scoring_run_id,
            )
        )
        .where(
            item.c.daily_feature_scoring_run_id == run.c.daily_feature_scoring_run_id,
            outcome.c.source_daily_feature_pipeline_run_id
            == run.c.source_daily_feature_pipeline_run_id,
            outcome.c.source_daily_feature_pipeline_item_id
            == item.c.source_daily_feature_pipeline_item_id,
            outcome.c.feature_snapshot_id == item.c.feature_snapshot_id,
            item.c.outcome == "SCORED_READY",
            item.c.source_quality_status == "READY",
            item.c.overall_relative_score.is_not(None),
            item.c.rank.is_not(None),
            outcome.c.horizon_trading_days == horizon.value,
            outcome.c.latest_input_available_at <= dataset_as_of,
            outcome.c.recorded_at <= dataset_as_of,
            run.c.generated_at <= dataset_as_of,
            item.c.recorded_at <= dataset_as_of,
            outcome.c.provider_code == SOURCE_PROVIDER_CODE,
            outcome.c.calendar_code == CALENDAR_CODE,
            outcome.c.calendar_version == CALENDAR_VERSION,
            outcome.c.outcome_policy_code == OUTCOME_POLICY_CODE,
            outcome.c.outcome_policy_version == OUTCOME_POLICY_VERSION,
            run.c.scoring_policy_code == SCORING_POLICY_CODE,
            run.c.scoring_policy_version == SCORING_POLICY_VERSION,
            run.c.ranking_policy_code == RANKING_POLICY_CODE,
            run.c.ranking_policy_version == RANKING_POLICY_VERSION,
        )
        .cte("eligible_calibration_outcome_revisions")
    )
    return (
        select(*(ranked.c[name] for name in _SOURCE_COLUMNS))
        .where(ranked.c.revision_rank == 1)
        .order_by(
            ranked.c.source_session_date.asc(),
            ranked.c.source_daily_feature_scoring_run_id.asc(),
            ranked.c.source_rank.asc(),
            ranked.c.mic_code.asc(),
            ranked.c.symbol.asc(),
            ranked.c.source_daily_feature_outcome_id.asc(),
        )
    )


def _allow_operation() -> None:
    return None


class SqlAlchemyProbabilityCalibrationDatasetSourceReader:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def list_eligible_sources(
        self,
        horizon: TradingDayHorizon,
        dataset_as_of: datetime,
        dataset_policy_code: CalibrationDatasetPolicyCode,
        dataset_policy_version: CalibrationDatasetPolicyVersion,
    ) -> tuple[CalibrationDatasetSourceRecord, ...]:
        self._ensure_active()
        if (dataset_policy_code.value, dataset_policy_version.value) != (
            DATASET_POLICY_CODE,
            DATASET_POLICY_VERSION,
        ):
            raise ValueError("P4B.2A dataset policy is unsupported")
        try:
            cutoff = normalize_utc(dataset_as_of)
        except (TypeError, ValidationError):
            raise ValueError("dataset_as_of must be timezone-aware") from None
        try:
            rows = (
                self._connection.execute(
                    eligible_calibration_dataset_sources_statement(horizon, cutoff)
                )
                .mappings()
                .all()
            )
            return tuple(map_calibration_dataset_source(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="probability_calibration_dataset_source", operation="select"
            ) from None
