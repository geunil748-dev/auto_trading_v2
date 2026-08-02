"""Safe row mapping for immutable P4B.1 forward outcomes."""

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.feature_outcomes import NewDailyFeatureOutcome
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import (
    DailyFeatureOutcome,
    ExcursionRate,
    ForwardReturn,
    FutureBarProvenanceEntry,
    OutcomeObservationMode,
    OutcomeObservationPolicyCode,
    OutcomeObservationPolicyVersion,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.market_calendar import (
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeaturePipelineItemID,
    DailyFeaturePipelineRunID,
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
    DailyMarketBarID,
    FeatureSnapshotID,
    SessionDate,
    Symbol,
    UtcTimestamp,
)

_PROVENANCE_KEYS = {
    "available_at",
    "content_digest",
    "daily_market_bar_id",
    "session_date",
    "source_code",
    "source_record_key",
    "source_version",
}


def map_daily_feature_outcome(row: Mapping[Any, Any]) -> DailyFeatureOutcome:
    try:
        return DailyFeatureOutcome(
            daily_feature_outcome_id=DailyFeatureOutcomeID(_uuid(row["daily_feature_outcome_id"])),
            outcome_key=_string(row["outcome_key"]),
            content_digest=_string(row["content_digest"]),
            path_revision_digest=_string(row["path_revision_digest"]),
            source_daily_feature_scoring_run_id=DailyFeatureScoringRunID(
                _uuid(row["source_daily_feature_scoring_run_id"])
            ),
            source_daily_feature_scoring_item_id=DailyFeatureScoringItemID(
                _uuid(row["source_daily_feature_scoring_item_id"])
            ),
            source_daily_feature_pipeline_run_id=DailyFeaturePipelineRunID(
                _uuid(row["source_daily_feature_pipeline_run_id"])
            ),
            source_daily_feature_pipeline_item_id=DailyFeaturePipelineItemID(
                _uuid(row["source_daily_feature_pipeline_item_id"])
            ),
            feature_snapshot_id=FeatureSnapshotID(_uuid(row["feature_snapshot_id"])),
            symbol=Symbol(_string(row["symbol"])),
            mic_code=_string(row["mic_code"]),
            provider_code=_string(row["provider_code"]),
            calendar_code=ExchangeCalendarCode(_string(row["calendar_code"])),
            calendar_version=ExchangeCalendarVersion(_string(row["calendar_version"])),
            source_session_date=SessionDate(_date(row["source_session_date"])),
            terminal_session_date=SessionDate(_date(row["terminal_session_date"])),
            horizon=TradingDayHorizon(_integer(row["horizon_trading_days"])),
            outcome_policy_code=OutcomeObservationPolicyCode(_string(row["outcome_policy_code"])),
            outcome_policy_version=OutcomeObservationPolicyVersion(
                _string(row["outcome_policy_version"])
            ),
            observation_as_of=_datetime(row["observation_as_of"]),
            reference_close=_decimal(row["reference_close"]),
            terminal_close=_decimal(row["terminal_close"]),
            forward_close_return=ForwardReturn(_decimal(row["forward_close_return"])),
            maximum_favorable_excursion_rate=ExcursionRate(
                _decimal(row["maximum_favorable_excursion_rate"])
            ),
            maximum_adverse_excursion_rate=ExcursionRate(
                _decimal(row["maximum_adverse_excursion_rate"])
            ),
            future_bar_count=_integer(row["future_bar_count"]),
            future_bar_provenance=_provenance(row["future_bar_provenance"]),
            latest_input_available_at=_datetime(row["latest_input_available_at"]),
            observation_mode=OutcomeObservationMode(_string(row["observation_mode"])),
            generated_at=_datetime(row["generated_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise PersistenceMappingError("daily_feature_outcome") from None


def new_daily_feature_outcome_values(candidate: NewDailyFeatureOutcome) -> dict[str, object]:
    value = candidate.outcome
    return {
        "daily_feature_outcome_id": value.daily_feature_outcome_id.value,
        "outcome_key": value.outcome_key,
        "content_digest": value.content_digest,
        "path_revision_digest": value.path_revision_digest,
        "source_daily_feature_scoring_run_id": value.source_daily_feature_scoring_run_id.value,
        "source_daily_feature_scoring_item_id": value.source_daily_feature_scoring_item_id.value,
        "source_daily_feature_pipeline_run_id": value.source_daily_feature_pipeline_run_id.value,
        "source_daily_feature_pipeline_item_id": value.source_daily_feature_pipeline_item_id.value,
        "feature_snapshot_id": value.feature_snapshot_id.value,
        "symbol": value.symbol.value,
        "mic_code": value.mic_code,
        "provider_code": value.provider_code,
        "calendar_code": value.calendar_code.value,
        "calendar_version": value.calendar_version.value,
        "source_session_date": value.source_session_date.value,
        "terminal_session_date": value.terminal_session_date.value,
        "horizon_trading_days": value.horizon.value,
        "outcome_policy_code": value.outcome_policy_code.value,
        "outcome_policy_version": value.outcome_policy_version.value,
        "observation_as_of": value.observation_as_of,
        "reference_close": value.reference_close,
        "terminal_close": value.terminal_close,
        "forward_close_return": value.forward_close_return.value,
        "maximum_favorable_excursion_rate": value.maximum_favorable_excursion_rate.value,
        "maximum_adverse_excursion_rate": value.maximum_adverse_excursion_rate.value,
        "future_bar_count": value.future_bar_count,
        "future_bar_provenance": json.dumps(
            [entry.as_json() for entry in value.future_bar_provenance],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "latest_input_available_at": value.latest_input_available_at,
        "observation_mode": value.observation_mode.value,
        "generated_at": value.generated_at,
    }


def _provenance(value: object) -> tuple[FutureBarProvenanceEntry, ...]:
    if not isinstance(value, str):
        raise TypeError
    raw = json.loads(value)
    if not isinstance(raw, list) or not raw:
        raise TypeError
    entries = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != _PROVENANCE_KEYS:
            raise TypeError
        entries.append(
            FutureBarProvenanceEntry(
                DailyMarketBarID.parse(_string(item["daily_market_bar_id"])),
                SessionDate.parse(_string(item["session_date"])),
                _string(item["source_code"]),
                _string(item["source_record_key"]),
                _string(item["source_version"]),
                UtcTimestamp.parse(_string(item["available_at"])).value,
                _string(item["content_digest"]),
            )
        )
    return tuple(entries)


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


def _decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
