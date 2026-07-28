"""Immutable creation and persistence contracts for Recommendation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.primitives import FeatureSnapshotID, RecommendationID
from auto_trading_v2.domain.recommendations import (
    Recommendation,
    RecommendationDisposition,
    RecommendationInput,
    RecommendationPlan,
    RecommendationValidationError,
    recommendation_content_digest,
    recommendation_key,
    validate_generated_at,
)


@dataclass(frozen=True, slots=True)
class CreateRecommendationCommand:
    """Caller input validated and frozen before orchestration starts."""

    feature_snapshot_id: FeatureSnapshotID
    generator_code: str
    generator_version: str
    disposition: RecommendationDisposition
    plan: RecommendationPlan | None = field(repr=False)
    reason_codes: Sequence[str]
    risk_codes: Sequence[str] = ()
    invalidation_codes: Sequence[str] = ()
    _recommendation_input: RecommendationInput = field(init=False, repr=False)

    def __post_init__(self) -> None:
        recommendation_input = RecommendationInput(
            feature_snapshot_id=self.feature_snapshot_id,
            generator_code=self.generator_code,
            generator_version=self.generator_version,
            disposition=self.disposition,
            plan=self.plan,
            reason_codes=self.reason_codes,
            risk_codes=self.risk_codes,
            invalidation_codes=self.invalidation_codes,
        )
        object.__setattr__(self, "_recommendation_input", recommendation_input)
        for name in (
            "feature_snapshot_id",
            "generator_code",
            "generator_version",
            "disposition",
            "plan",
            "reason_codes",
            "risk_codes",
            "invalidation_codes",
        ):
            object.__setattr__(self, name, getattr(recommendation_input, name))

    @property
    def recommendation_input(self) -> RecommendationInput:
        return self._recommendation_input


@dataclass(frozen=True, slots=True)
class NewRecommendation:
    """Insert-only contract; recorded_at remains database-owned."""

    recommendation_id: RecommendationID
    recommendation_key: str
    content_digest: str
    recommendation_input: RecommendationInput = field(repr=False)
    generated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.recommendation_id, RecommendationID):
            raise RecommendationValidationError("recommendation_id 타입이 올바르지 않습니다.")
        if not isinstance(self.recommendation_input, RecommendationInput):
            raise RecommendationValidationError("recommendation_input 타입이 올바르지 않습니다.")
        generated_at = validate_generated_at(self.recommendation_input, self.generated_at)
        if self.recommendation_key != recommendation_key(self.recommendation_input):
            raise RecommendationValidationError(
                "recommendation_key가 semantic identity와 다릅니다."
            )
        if self.content_digest != recommendation_content_digest(self.recommendation_input):
            raise RecommendationValidationError("content_digest가 Recommendation 내용과 다릅니다.")
        object.__setattr__(self, "generated_at", generated_at)

    def stored(self, recorded_at: datetime) -> Recommendation:
        return Recommendation(
            recommendation_id=self.recommendation_id,
            recommendation_key=self.recommendation_key,
            content_digest=self.content_digest,
            recommendation_input=self.recommendation_input,
            generated_at=self.generated_at,
            recorded_at=recorded_at,
        )


class RecommendationCreationOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class RecommendationCreationResult:
    outcome: RecommendationCreationOutcome
    recommendation: Recommendation
