"""Deterministic semantic identity and content digest for pipeline runs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn

from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_pipeline.errors import (
    DailyFeaturePipelineValidationError,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.market_calendar import (
    CompletionGracePeriod,
    ExchangeCalendarCode,
    ExchangeCalendarVersion,
)
from auto_trading_v2.domain.primitives import SessionDate, UniverseSnapshotID
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc

PIPELINE_CODE = "US_EQUITY_DAILY_FEATURE_BATCH"
PIPELINE_VERSION = "v1"
FEATURE_SET_CODE = "US_EQUITY_DAILY_TECHNICAL"
FEATURE_SET_VERSION = "v1"
PIPELINE_VERSION_V2 = "v2"
FEATURE_SET_VERSION_V2 = "v2"
MIN_REQUESTED_SESSIONS = 21
DEFAULT_REQUESTED_SESSIONS = 30
TRANSIENT_FAILURE_LIMIT = 3
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelinePolicy:
    pipeline_code: str
    pipeline_version: str
    feature_set_code: str
    feature_set_version: str

    def __post_init__(self) -> None:
        if (
            self.pipeline_code,
            self.pipeline_version,
            self.feature_set_code,
            self.feature_set_version,
        ) not in _SUPPORTED_CONTRACTS:
            _invalid("PIPELINE_CONTRACT_VERSION_INVALID")


_SUPPORTED_CONTRACTS = frozenset(
    {
        (PIPELINE_CODE, PIPELINE_VERSION, FEATURE_SET_CODE, FEATURE_SET_VERSION),
        (PIPELINE_CODE, PIPELINE_VERSION_V2, FEATURE_SET_CODE, FEATURE_SET_VERSION_V2),
    }
)
DAILY_FEATURE_PIPELINE_POLICY_V1 = DailyFeaturePipelinePolicy(
    PIPELINE_CODE, PIPELINE_VERSION, FEATURE_SET_CODE, FEATURE_SET_VERSION
)
DAILY_FEATURE_PIPELINE_POLICY_V2 = DailyFeaturePipelinePolicy(
    PIPELINE_CODE, PIPELINE_VERSION_V2, FEATURE_SET_CODE, FEATURE_SET_VERSION_V2
)


@dataclass(frozen=True, slots=True)
class DailyFeaturePipelineIdentity:
    universe_snapshot_id: UniverseSnapshotID
    provider_code: str
    calendar_code: ExchangeCalendarCode
    calendar_version: ExchangeCalendarVersion
    completed_session_date: SessionDate | None
    adjustment_basis: DailyMarketBarAdjustmentBasis
    horizon: TradingDayHorizon
    requested_session_count: int
    as_of: datetime
    completion_grace: CompletionGracePeriod
    pipeline_code: str = PIPELINE_CODE
    pipeline_version: str = PIPELINE_VERSION
    feature_set_code: str = FEATURE_SET_CODE
    feature_set_version: str = FEATURE_SET_VERSION

    def __post_init__(self) -> None:
        checks = (
            (self.universe_snapshot_id, UniverseSnapshotID, "PIPELINE_UNIVERSE_ID_INVALID"),
            (self.calendar_code, ExchangeCalendarCode, "PIPELINE_CALENDAR_CODE_INVALID"),
            (
                self.calendar_version,
                ExchangeCalendarVersion,
                "PIPELINE_CALENDAR_VERSION_INVALID",
            ),
            (self.horizon, TradingDayHorizon, "PIPELINE_HORIZON_INVALID"),
            (
                self.completion_grace,
                CompletionGracePeriod,
                "PIPELINE_COMPLETION_GRACE_INVALID",
            ),
        )
        for value, expected, category in checks:
            if not isinstance(value, expected):
                _invalid(category)
        if not isinstance(self.provider_code, str) or not _CODE.fullmatch(
            self.provider_code.strip()
        ):
            _invalid("PIPELINE_PROVIDER_CODE_INVALID")
        if self.completed_session_date is not None and not isinstance(
            self.completed_session_date, SessionDate
        ):
            _invalid("PIPELINE_SESSION_DATE_INVALID")
        if self.adjustment_basis is not DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED:
            _invalid("PIPELINE_ADJUSTMENT_BASIS_INVALID")
        if (
            isinstance(self.requested_session_count, bool)
            or not isinstance(self.requested_session_count, int)
            or self.requested_session_count < MIN_REQUESTED_SESSIONS
        ):
            _invalid("PIPELINE_REQUESTED_SESSIONS_INVALID")
        if (
            self.pipeline_code,
            self.pipeline_version,
            self.feature_set_code,
            self.feature_set_version,
        ) not in _SUPPORTED_CONTRACTS:
            _invalid("PIPELINE_CONTRACT_VERSION_INVALID")
        try:
            as_of = normalize_utc(self.as_of)
        except (TypeError, ValidationError):
            _invalid("PIPELINE_AS_OF_INVALID")
        object.__setattr__(self, "provider_code", self.provider_code.strip())
        object.__setattr__(self, "as_of", as_of)


def daily_feature_run_key(identity: DailyFeaturePipelineIdentity) -> str:
    completed = (
        "NO_COMPLETED_SESSION"
        if identity.completed_session_date is None
        else identity.completed_session_date.serialize()
    )
    payload = {
        "adjustment_basis": identity.adjustment_basis.value,
        "as_of": UtcTimestamp(identity.as_of).serialize(),
        "calendar_code": identity.calendar_code.value,
        "calendar_version": identity.calendar_version.value,
        "completed_session_date": completed,
        "completion_grace_seconds": int(identity.completion_grace.value.total_seconds()),
        "feature_set_code": identity.feature_set_code,
        "feature_set_version": identity.feature_set_version,
        "horizon_trading_days": identity.horizon.value,
        "pipeline_code": identity.pipeline_code,
        "pipeline_version": identity.pipeline_version,
        "provider_code": identity.provider_code,
        "requested_session_count": identity.requested_session_count,
        "universe_snapshot_id": identity.universe_snapshot_id.serialize(),
    }
    return f"daily-feature-run:v1:{_sha256(_canonical_json(payload))}"


def pipeline_content_digest(payload: object) -> str:
    return _sha256(_canonical_json(payload))


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _invalid(category: str) -> NoReturn:
    raise DailyFeaturePipelineValidationError(category)
