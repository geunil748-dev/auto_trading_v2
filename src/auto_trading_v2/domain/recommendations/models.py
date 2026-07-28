"""Immutable canonical Recommendation identity, content, and stored record."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots import canonical_json
from auto_trading_v2.domain.primitives import FeatureSnapshotID, RecommendationID
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.recommendations.codes import (
    canonical_codes,
    normalize_generator_code,
)
from auto_trading_v2.domain.recommendations.errors import (
    RecommendationValidationError,
)
from auto_trading_v2.domain.recommendations.plans import (
    RecommendationDisposition,
    RecommendationPlan,
)

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_KEY_PATTERN = re.compile(r"^recommendation:v1:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RecommendationInput:
    """Validated identity and content supplied by a recommendation generator."""

    feature_snapshot_id: FeatureSnapshotID
    generator_code: str
    generator_version: str
    disposition: RecommendationDisposition
    plan: RecommendationPlan | None = field(repr=False)
    reason_codes: Sequence[str]
    risk_codes: Sequence[str] = ()
    invalidation_codes: Sequence[str] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.feature_snapshot_id, FeatureSnapshotID):
            raise RecommendationValidationError("feature_snapshot_id 타입이 올바르지 않습니다.")
        if not isinstance(self.disposition, RecommendationDisposition):
            raise RecommendationValidationError("disposition 타입이 올바르지 않습니다.")
        object.__setattr__(
            self,
            "generator_code",
            normalize_generator_code(self.generator_code, "generator_code"),
        )
        object.__setattr__(
            self,
            "generator_version",
            normalize_generator_code(self.generator_version, "generator_version"),
        )
        if self.disposition.actionable != isinstance(self.plan, RecommendationPlan):
            message = (
                "actionable Recommendation에는 plan이 필요합니다."
                if self.disposition.actionable
                else "non-actionable Recommendation은 plan을 가질 수 없습니다."
            )
            raise RecommendationValidationError(message)
        reasons = canonical_codes(self.reason_codes, "reason_codes")
        risks = canonical_codes(self.risk_codes, "risk_codes")
        invalidations = canonical_codes(self.invalidation_codes, "invalidation_codes")
        if not reasons:
            raise RecommendationValidationError("reason_codes는 비어 있을 수 없습니다.")
        if (
            self.disposition.actionable or self.disposition is RecommendationDisposition.MARKET_RISK
        ) and not risks:
            raise RecommendationValidationError("이 disposition에는 risk_codes가 필요합니다.")
        if self.disposition.actionable and not invalidations:
            raise RecommendationValidationError(
                "actionable Recommendation에는 무효화 코드가 필요합니다."
            )
        if not self.disposition.actionable and invalidations:
            raise RecommendationValidationError(
                "non-actionable Recommendation의 무효화 코드는 비어 있어야 합니다."
            )
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "risk_codes", risks)
        object.__setattr__(self, "invalidation_codes", invalidations)


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Canonical immutable stored Recommendation record."""

    recommendation_id: RecommendationID
    recommendation_key: str
    content_digest: str
    recommendation_input: RecommendationInput = field(repr=False)
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.recommendation_id, RecommendationID):
            raise RecommendationValidationError("recommendation_id 타입이 올바르지 않습니다.")
        if not isinstance(self.recommendation_input, RecommendationInput):
            raise RecommendationValidationError("recommendation_input 타입이 올바르지 않습니다.")
        generated_at = _timestamp(self.generated_at, "generated_at")
        recorded_at = _timestamp(self.recorded_at, "recorded_at")
        _validate_generated_plan(self.recommendation_input, generated_at)
        if not _KEY_PATTERN.fullmatch(self.recommendation_key):
            raise RecommendationValidationError("recommendation_key 형식이 올바르지 않습니다.")
        if not _DIGEST_PATTERN.fullmatch(self.content_digest):
            raise RecommendationValidationError("content_digest 형식이 올바르지 않습니다.")
        if self.recommendation_key != recommendation_key(self.recommendation_input):
            raise RecommendationValidationError(
                "recommendation_key가 semantic identity와 다릅니다."
            )
        if self.content_digest != recommendation_content_digest(self.recommendation_input):
            raise RecommendationValidationError("content_digest가 Recommendation 내용과 다릅니다.")
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "recorded_at", recorded_at)


def recommendation_key(recommendation_input: RecommendationInput) -> str:
    """Hash only the semantic identity, never recommendation content."""

    identity = {
        "feature_snapshot_id": recommendation_input.feature_snapshot_id.serialize(),
        "generator_code": recommendation_input.generator_code,
        "generator_version": recommendation_input.generator_version,
    }
    return f"recommendation:v1:{_sha256(canonical_json(identity))}"


def recommendation_content_digest(recommendation_input: RecommendationInput) -> str:
    """Hash only the canonical decision content, excluding identity and timestamps."""

    content = {
        "disposition": recommendation_input.disposition.value,
        "invalidation_codes": list(recommendation_input.invalidation_codes),
        "plan": None if recommendation_input.plan is None else recommendation_input.plan.as_json(),
        "reason_codes": list(recommendation_input.reason_codes),
        "risk_codes": list(recommendation_input.risk_codes),
    }
    return _sha256(canonical_json(content))


def validate_generated_at(
    recommendation_input: RecommendationInput,
    generated_at: datetime,
) -> datetime:
    """Validate a generated timestamp before an insert contract is created."""

    normalized = _timestamp(generated_at, "generated_at")
    _validate_generated_plan(recommendation_input, normalized)
    return normalized


def _validate_generated_plan(
    recommendation_input: RecommendationInput,
    generated_at: datetime,
) -> None:
    plan = recommendation_input.plan
    if plan is not None and plan.valid_until <= generated_at:
        raise RecommendationValidationError("valid_until은 generated_at 이후여야 합니다.")


def _timestamp(value: datetime, label: str) -> datetime:
    try:
        return normalize_utc(value)
    except ValidationError:
        raise RecommendationValidationError(
            f"{label}은 timezone-aware datetime이어야 합니다."
        ) from None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
