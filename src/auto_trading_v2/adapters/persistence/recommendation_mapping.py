"""Safe row mapping and code serialization for Recommendations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon, canonical_json
from auto_trading_v2.domain.primitives import (
    Currency,
    FeatureSnapshotID,
    Price,
    Rate,
    RecommendationID,
)
from auto_trading_v2.domain.recommendations import (
    Recommendation,
    RecommendationDisposition,
    RecommendationInput,
    RecommendationPlan,
    RecommendationValidationError,
)


def serialize_codes(values: Sequence[str]) -> str:
    return canonical_json(list(values))


def map_recommendation(row: Mapping[Any, Any]) -> Recommendation:
    """Map one row without retaining rejected JSON payloads in an error."""

    try:
        disposition = RecommendationDisposition(_string(row["disposition"]))
        recommendation_input = RecommendationInput(
            feature_snapshot_id=FeatureSnapshotID(_uuid(row["feature_snapshot_id"])),
            generator_code=_string(row["generator_code"]),
            generator_version=_string(row["generator_version"]),
            disposition=disposition,
            plan=_plan(row, disposition),
            reason_codes=_code_array(row["reason_codes"]),
            risk_codes=_code_array(row["risk_codes"]),
            invalidation_codes=_code_array(row["invalidation_codes"]),
        )
        return Recommendation(
            recommendation_id=RecommendationID(_uuid(row["recommendation_id"])),
            recommendation_key=_string(row["recommendation_key"]),
            content_digest=_string(row["content_digest"]),
            recommendation_input=recommendation_input,
            generated_at=_datetime(row["generated_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        RecommendationValidationError,
    ):
        raise PersistenceMappingError("recommendation") from None


def _plan(
    row: Mapping[Any, Any],
    disposition: RecommendationDisposition,
) -> RecommendationPlan | None:
    if not disposition.actionable:
        if any(row[name] is not None for name in _PLAN_COLUMNS):
            raise TypeError
        return None
    return RecommendationPlan(
        currency=Currency(_string(row["currency"])),
        entry_price_low=Price(_decimal(row["entry_price_low"])),
        entry_price_high=Price(_decimal(row["entry_price_high"])),
        target_price=Price(_decimal(row["target_price"])),
        stop_price=Price(_decimal(row["stop_price"])),
        expected_holding_trading_days=TradingDayHorizon(
            _integer(row["expected_holding_trading_days"])
        ),
        upside_probability=Rate(_decimal(row["upside_probability"])),
        target_probability=Rate(_decimal(row["target_probability"])),
        stop_probability=Rate(_decimal(row["stop_probability"])),
        expected_value_rate=Rate(_decimal(row["expected_value_rate"])),
        reward_risk_ratio=Rate(_decimal(row["reward_risk_ratio"])),
        confidence=Rate(_decimal(row["confidence"])),
        valid_until=_datetime(row["valid_until"]),
    )


def _code_array(value: object) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise TypeError
    decoded = json.loads(value)
    if not isinstance(decoded, list) or any(not isinstance(item, str) for item in decoded):
        raise TypeError
    return tuple(decoded)


def _decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError
    return value


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


_PLAN_COLUMNS = (
    "currency",
    "entry_price_low",
    "entry_price_high",
    "target_price",
    "stop_price",
    "expected_holding_trading_days",
    "upside_probability",
    "target_probability",
    "stop_probability",
    "expected_value_rate",
    "reward_risk_ratio",
    "confidence",
    "valid_until",
)
