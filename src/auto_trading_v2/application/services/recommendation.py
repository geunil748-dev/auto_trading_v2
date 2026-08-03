"""Atomic, idempotent Recommendation creation from one FeatureSnapshot."""

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.recommendations import (
    CreateRecommendationCommand,
    NewRecommendation,
    RecommendationCreationOutcome,
    RecommendationCreationResult,
)
from auto_trading_v2.application.errors import DuplicateRecordError
from auto_trading_v2.application.ports.id_factory import RecommendationIDFactory
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.recommendation_errors import (
    RecommendationConflictError,
    RecommendationRaceResolutionError,
    RecommendationSourceNotFoundError,
    RecommendationSourceRejectedError,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, FeatureSnapshot
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.recommendations import (
    Recommendation,
    RecommendationInput,
    RecommendationValidationError,
    recommendation_content_digest,
    recommendation_key,
    validate_generated_at,
)
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class RecommendationCreationService:
    """Create once, return exact retries, and reject source/content conflicts."""

    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock
    recommendation_id_factory: RecommendationIDFactory

    def create(self, command: CreateRecommendationCommand) -> RecommendationCreationResult:
        if not isinstance(command, CreateRecommendationCommand):
            raise RecommendationValidationError("Recommendation 생성 command가 필요합니다.")
        recommendation_input = command.recommendation_input
        generated_at = self._generated_at()
        validate_generated_at(recommendation_input, generated_at)

        raced = False
        with self.unit_of_work_factory() as unit_of_work:
            source = unit_of_work.feature_snapshots.get_by_id(
                recommendation_input.feature_snapshot_id
            )
            self._validate_source(source, recommendation_input, generated_at)
            key = recommendation_key(recommendation_input)
            digest = recommendation_content_digest(recommendation_input)
            existing = unit_of_work.recommendations.get_by_recommendation_key(key)
            if existing is not None:
                return self._existing_result(existing, digest)
            new_recommendation = NewRecommendation(
                recommendation_id=self.recommendation_id_factory.new(),
                recommendation_key=key,
                content_digest=digest,
                recommendation_input=recommendation_input,
                generated_at=generated_at,
            )
            try:
                stored = unit_of_work.recommendations.add(new_recommendation)
            except DuplicateRecordError:
                unit_of_work.rollback()
                raced = True
            else:
                unit_of_work.commit()
                return RecommendationCreationResult(
                    RecommendationCreationOutcome.CREATED,
                    stored,
                )
        if not raced:
            raise RecommendationRaceResolutionError()
        return self._resolve_unique_race(key, digest)

    def _resolve_unique_race(
        self,
        key: str,
        digest: str,
    ) -> RecommendationCreationResult:
        with self.unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.recommendations.get_by_recommendation_key(key)
            if existing is None:
                raise RecommendationRaceResolutionError()
            return self._existing_result(existing, digest)

    def _generated_at(self) -> datetime:
        try:
            return normalize_utc(self.clock.now_utc())
        except ValidationError:
            raise RecommendationValidationError(
                "generated_at은 timezone-aware datetime이어야 합니다."
            ) from None

    @staticmethod
    def _validate_source(
        source: FeatureSnapshot | None,
        recommendation_input: RecommendationInput,
        generated_at: datetime,
    ) -> None:
        if source is None:
            raise RecommendationSourceNotFoundError(recommendation_input.feature_snapshot_id)
        if source.feature_snapshot_id != recommendation_input.feature_snapshot_id:
            raise RecommendationSourceRejectedError("SOURCE_ID_MISMATCH")
        if generated_at < source.snapshot_input.as_of:
            raise RecommendationSourceRejectedError("GENERATED_BEFORE_SOURCE")
        if (
            recommendation_input.disposition.actionable
            and source.snapshot_input.quality_status is not FeatureQualityStatus.READY
        ):
            raise RecommendationSourceRejectedError("SOURCE_NOT_READY")
        plan = recommendation_input.plan
        if (
            plan is not None
            and plan.expected_holding_trading_days.value > source.snapshot_input.horizon.value
        ):
            raise RecommendationSourceRejectedError("HORIZON_EXCEEDED")

    @staticmethod
    def _existing_result(
        existing: Recommendation,
        digest: str,
    ) -> RecommendationCreationResult:
        if existing.content_digest != digest:
            raise RecommendationConflictError(existing.recommendation_key)
        return RecommendationCreationResult(
            RecommendationCreationOutcome.ALREADY_EXISTS,
            existing,
        )
