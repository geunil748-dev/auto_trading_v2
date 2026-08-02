"""Safe row mapping for P4B.1 observation runs and items."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.feature_outcomes import (
    NewDailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcomeObservationRun,
    DailyFeatureOutcomeObservationRunItem,
    DailyFeatureOutcomeObservationRunItemOutcome,
    DailyFeatureOutcomeObservationRunStatus,
    OutcomeObservationPolicyCode,
    OutcomeObservationPolicyVersion,
    OutcomeObservationRunIdentity,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeObservationRunID,
    DailyFeatureOutcomeObservationRunItemID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    SessionDate,
)


def map_outcome_observation_run(row: Mapping[Any, Any]) -> DailyFeatureOutcomeObservationRun:
    try:
        identity = OutcomeObservationRunIdentity(
            DailyFeatureScoringRunID(_uuid(row["source_daily_feature_scoring_run_id"])),
            OutcomeObservationPolicyCode(_string(row["outcome_policy_code"])),
            OutcomeObservationPolicyVersion(_string(row["outcome_policy_version"])),
            _datetime(row["observation_as_of"]),
            _integer(row["completion_grace_seconds"]),
        )
        return DailyFeatureOutcomeObservationRun(
            DailyFeatureOutcomeObservationRunID(
                _uuid(row["daily_feature_outcome_observation_run_id"])
            ),
            _string(row["observation_run_key"]),
            _string(row["content_digest"]),
            identity,
            DailyFeatureOutcomeObservationRunStatus(_string(row["status"])),
            _integer(row["total_count"]),
            _integer(row["outcome_created_count"]),
            _integer(row["outcome_existing_count"]),
            _integer(row["not_matured_count"]),
            _integer(row["incomplete_count"]),
            _integer(row["ineligible_count"]),
            _integer(row["invalid_count"]),
            _datetime(row["generated_at"]),
            _datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("daily_feature_outcome_observation_run") from None


def map_outcome_observation_item(
    row: Mapping[Any, Any],
) -> DailyFeatureOutcomeObservationRunItem:
    try:
        raw_outcome_id = row["daily_feature_outcome_id"]
        raw_terminal = row["terminal_session_date"]
        raw_reason = row["safe_reason_code"]
        return DailyFeatureOutcomeObservationRunItem(
            DailyFeatureOutcomeObservationRunItemID(
                _uuid(row["daily_feature_outcome_observation_run_item_id"])
            ),
            DailyFeatureOutcomeObservationRunID(
                _uuid(row["daily_feature_outcome_observation_run_id"])
            ),
            DailyFeatureScoringItemID(_uuid(row["source_daily_feature_scoring_item_id"])),
            _integer(row["ordinal"]),
            DailyFeatureOutcomeObservationRunItemOutcome(_string(row["outcome"])),
            None if raw_outcome_id is None else DailyFeatureOutcomeID(_uuid(raw_outcome_id)),
            None if raw_terminal is None else SessionDate(_date(raw_terminal)),
            None if raw_reason is None else _string(raw_reason),
            _datetime(row["generated_at"]),
            _datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("daily_feature_outcome_observation_run_item") from None


def new_outcome_observation_run_values(
    candidate: NewDailyFeatureOutcomeObservationRunWithItems,
) -> dict[str, object]:
    run = candidate.aggregate.run
    identity = run.identity
    return {
        "daily_feature_outcome_observation_run_id": (
            run.daily_feature_outcome_observation_run_id.value
        ),
        "observation_run_key": run.observation_run_key,
        "content_digest": run.content_digest,
        "source_daily_feature_scoring_run_id": identity.source_daily_feature_scoring_run_id.value,
        "outcome_policy_code": identity.outcome_policy_code.value,
        "outcome_policy_version": identity.outcome_policy_version.value,
        "observation_as_of": identity.observation_as_of,
        "completion_grace_seconds": identity.completion_grace_seconds,
        "status": run.status.value,
        "total_count": run.total_count,
        "outcome_created_count": run.outcome_created_count,
        "outcome_existing_count": run.outcome_existing_count,
        "not_matured_count": run.not_matured_count,
        "incomplete_count": run.incomplete_count,
        "ineligible_count": run.ineligible_count,
        "invalid_count": run.invalid_count,
        "generated_at": run.generated_at,
    }


def new_outcome_observation_item_values(
    item: DailyFeatureOutcomeObservationRunItem,
) -> dict[str, object]:
    return {
        "daily_feature_outcome_observation_run_item_id": (
            item.daily_feature_outcome_observation_run_item_id.value
        ),
        "daily_feature_outcome_observation_run_id": (
            item.daily_feature_outcome_observation_run_id.value
        ),
        "source_daily_feature_scoring_item_id": item.source_daily_feature_scoring_item_id.value,
        "ordinal": item.ordinal,
        "outcome": item.outcome.value,
        "daily_feature_outcome_id": None
        if item.daily_feature_outcome_id is None
        else item.daily_feature_outcome_id.value,
        "terminal_session_date": None
        if item.terminal_session_date is None
        else item.terminal_session_date.value,
        "safe_reason_code": item.safe_reason_code,
        "generated_at": item.generated_at,
    }


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _date(value: object) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
