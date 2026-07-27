from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from auto_trading_v2.application.contracts.recommendations import (
    CreateRecommendationCommand,
    NewRecommendation,
)
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import FeatureSnapshotID, RecommendationID
from auto_trading_v2.domain.recommendations import (
    Recommendation,
    RecommendationDisposition,
    recommendation_content_digest,
    recommendation_key,
)
from tests.unit.application.feature_snapshot_fakes import command as snapshot_command
from tests.unit.application.feature_snapshot_fakes import stored_for
from tests.unit.domain.recommendations.helpers import plan

GENERATED_AT = datetime(2026, 7, 28, 5, tzinfo=UTC)


def feature_snapshot(*, degraded: bool = False, identifier: int = 1) -> object:
    source = snapshot_command()
    if degraded:
        source = type(source)(
            symbol=source.symbol,
            feature_set_code=source.feature_set_code,
            feature_set_version=source.feature_set_version,
            horizon=source.horizon,
            as_of=source.as_of,
            feature_values=source.feature_values,
            provenance=source.provenance,
            quality_status=FeatureQualityStatus.DEGRADED,
            quality_reason_codes=("SOURCE_DELAYED",),
        )
    return stored_for(source, identifier=identifier, generated_at=GENERATED_AT)


def command(
    *,
    disposition: RecommendationDisposition = RecommendationDisposition.RECOMMEND,
    reason_codes: tuple[str, ...] = ("EXPECTED_VALUE_POSITIVE",),
    selected_plan: object = ...,
) -> CreateRecommendationCommand:
    if selected_plan is ...:
        selected_plan = plan() if disposition.actionable else None
    return CreateRecommendationCommand(
        feature_snapshot_id=FeatureSnapshotID(UUID(int=1)),
        generator_code="RULE_ENGINE",
        generator_version="v1",
        disposition=disposition,
        plan=selected_plan,
        reason_codes=reason_codes,
        risk_codes=("MARKET_VOLATILITY",)
        if disposition.actionable or disposition is RecommendationDisposition.MARKET_RISK
        else (),
        invalidation_codes=("STOP_BREACH",) if disposition.actionable else (),
    )


def stored_recommendation(
    source: CreateRecommendationCommand,
    *,
    identifier: int = 10,
) -> Recommendation:
    recommendation_input = source.recommendation_input
    return NewRecommendation(
        recommendation_id=RecommendationID(UUID(int=identifier)),
        recommendation_key=recommendation_key(recommendation_input),
        content_digest=recommendation_content_digest(recommendation_input),
        recommendation_input=recommendation_input,
        generated_at=GENERATED_AT,
    ).stored(GENERATED_AT)


class RecordingClock:
    def __init__(self, value: datetime = GENERATED_AT) -> None:
        self.value = value
        self.calls = 0

    def now_utc(self) -> datetime:
        self.calls += 1
        return self.value


class RecordingIDFactory:
    def __init__(self) -> None:
        self.calls = 0

    def new(self) -> RecommendationID:
        self.calls += 1
        return RecommendationID(UUID(int=100 + self.calls))


class FakeFeatureSnapshotRepository:
    def __init__(self, source: object | None) -> None:
        self.source = source
        self.calls = 0

    def get_by_id(self, feature_snapshot_id: FeatureSnapshotID) -> object | None:
        self.calls += 1
        return self.source


class FakeRecommendationRepository:
    def __init__(
        self,
        existing: Recommendation | None = None,
        *,
        duplicate_on_add: bool = False,
        failure: str | None = None,
    ) -> None:
        self.existing = existing
        self.duplicate_on_add = duplicate_on_add
        self.failure = failure
        self.add_calls: list[NewRecommendation] = []

    def get_by_recommendation_key(self, key: str) -> Recommendation | None:
        if self.failure == "get":
            raise PersistenceError(entity="recommendation", operation="select")
        if self.existing is not None and self.existing.recommendation_key == key:
            return self.existing
        return None

    def add(self, recommendation: NewRecommendation) -> Recommendation:
        self.add_calls.append(recommendation)
        if self.failure == "add":
            raise PersistenceError(entity="recommendation", operation="insert")
        if self.duplicate_on_add:
            raise DuplicateRecordError(
                entity="recommendation",
                operation="insert",
                reason="duplicate_record",
            )
        self.existing = recommendation.stored(GENERATED_AT)
        return self.existing


class FakeUnitOfWork:
    def __init__(
        self,
        source: object | None,
        recommendations: FakeRecommendationRepository,
    ) -> None:
        self.feature_snapshots = FakeFeatureSnapshotRepository(source)
        self.recommendations = recommendations
        self.commit_calls = 0
        self.rollback_calls = 0
        self.finished = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def commit(self) -> None:
        self.commit_calls += 1
        self.finished = True

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.finished:
            self.rollback()


@dataclass
class FakeUnitOfWorkFactory:
    unit_of_works: list[FakeUnitOfWork]
    calls: int = 0

    def __call__(self) -> FakeUnitOfWork:
        result = self.unit_of_works[self.calls]
        self.calls += 1
        return result
