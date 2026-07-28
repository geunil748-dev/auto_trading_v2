"""SQLAlchemy Core repository for immutable Recommendation records."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.recommendation_mapping import (
    map_recommendation,
    serialize_codes,
)
from auto_trading_v2.adapters.persistence.tables import recommendations
from auto_trading_v2.application.contracts.recommendations import NewRecommendation
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import FeatureSnapshotID, RecommendationID
from auto_trading_v2.domain.recommendations import Recommendation, RecommendationPlan


def _allow_operation() -> None:
    return None


class SqlAlchemyRecommendationRepository:
    """Insert and read Recommendations in the caller-owned transaction."""

    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, recommendation: NewRecommendation) -> Recommendation:
        self._ensure_active()
        source = recommendation.recommendation_input
        values = {
            "recommendation_id": recommendation.recommendation_id.value,
            "recommendation_key": recommendation.recommendation_key,
            "content_digest": recommendation.content_digest,
            "feature_snapshot_id": source.feature_snapshot_id.value,
            "generator_code": source.generator_code,
            "generator_version": source.generator_version,
            "disposition": source.disposition.value,
            **_plan_values(source.plan),
            "reason_codes": serialize_codes(source.reason_codes),
            "risk_codes": serialize_codes(source.risk_codes),
            "invalidation_codes": serialize_codes(source.invalidation_codes),
            "generated_at": recommendation.generated_at,
        }
        try:
            self._connection.execute(recommendations.insert().values(**values))
            stored = self._select_by_id(recommendation.recommendation_id)
            if stored is None:
                raise PersistenceMappingError("recommendation", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="recommendation",
                operation="insert",
            ) from None

    def get_by_id(self, recommendation_id: RecommendationID) -> Recommendation | None:
        self._ensure_active()
        try:
            return self._select_by_id(recommendation_id)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="recommendation",
                operation="select",
            ) from None

    def get_by_recommendation_key(
        self,
        recommendation_key: str,
    ) -> Recommendation | None:
        self._ensure_active()
        try:
            row = (
                self._connection.execute(
                    select(recommendations).where(
                        recommendations.c.recommendation_key == recommendation_key
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else map_recommendation(row)
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc,
                entity="recommendation",
                operation="select",
            ) from None

    def list_by_feature_snapshot_id(
        self,
        feature_snapshot_id: FeatureSnapshotID,
    ) -> tuple[Recommendation, ...]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(recommendations)
                    .where(recommendations.c.feature_snapshot_id == feature_snapshot_id.value)
                    .order_by(
                        recommendations.c.generated_at,
                        recommendations.c.recommendation_id,
                    )
                )
                .mappings()
                .all()
            )
            return tuple(map_recommendation(row) for row in rows)
        except (PersistenceMappingError, SQLAlchemyError) as exc:
            self._mark_failed()
            if isinstance(exc, PersistenceMappingError):
                raise
            raise translate_persistence_error(
                exc,
                entity="recommendation",
                operation="select",
            ) from None

    def _select_by_id(
        self,
        recommendation_id: RecommendationID,
    ) -> Recommendation | None:
        row = (
            self._connection.execute(
                select(recommendations).where(
                    recommendations.c.recommendation_id == recommendation_id.value
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_recommendation(row)


def _plan_values(plan: RecommendationPlan | None) -> dict[str, object]:
    columns: dict[str, object] = {
        "currency": None,
        "entry_price_low": None,
        "entry_price_high": None,
        "target_price": None,
        "stop_price": None,
        "expected_holding_trading_days": None,
        "upside_probability": None,
        "target_probability": None,
        "stop_probability": None,
        "expected_value_rate": None,
        "reward_risk_ratio": None,
        "confidence": None,
        "valid_until": None,
    }
    if plan is None:
        return columns
    columns.update(
        {
            "currency": plan.currency.code,
            "entry_price_low": plan.entry_price_low.value,
            "entry_price_high": plan.entry_price_high.value,
            "target_price": plan.target_price.value,
            "stop_price": plan.stop_price.value,
            "expected_holding_trading_days": plan.expected_holding_trading_days.value,
            "upside_probability": plan.upside_probability.value,
            "target_probability": plan.target_probability.value,
            "stop_probability": plan.stop_probability.value,
            "expected_value_rate": plan.expected_value_rate.value,
            "reward_risk_ratio": plan.reward_risk_ratio.value,
            "confidence": plan.confidence.value,
            "valid_until": plan.valid_until,
        }
    )
    return columns
