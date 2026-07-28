from datetime import UTC, datetime
from inspect import getmembers, isfunction
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy import CheckConstraint, Connection, ForeignKeyConstraint, UniqueConstraint

from auto_trading_v2.adapters.persistence.recommendation_mapping import (
    map_recommendation,
    serialize_codes,
)
from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyRecommendationRepository,
)
from auto_trading_v2.adapters.persistence.tables import recommendations
from auto_trading_v2.application.contracts.recommendations import NewRecommendation
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.ports.recommendations import RecommendationRepository
from auto_trading_v2.domain.primitives import (
    FeatureSnapshotID,
    RecommendationID,
)
from auto_trading_v2.domain.recommendations import (
    RecommendationDisposition,
    recommendation_content_digest,
    recommendation_key,
)
from tests.unit.domain.recommendations.helpers import (
    GENERATED_AT,
    recommendation_input,
)


def _new_recommendation(
    disposition: RecommendationDisposition = RecommendationDisposition.RECOMMEND,
) -> NewRecommendation:
    source = recommendation_input(
        disposition=disposition,
        risk_codes=()
        if disposition
        in {
            RecommendationDisposition.WATCH,
            RecommendationDisposition.NO_RECOMMENDATION,
            RecommendationDisposition.DATA_INSUFFICIENT,
        }
        else ("MARKET_VOLATILITY",),
        invalidation_codes=() if not disposition.actionable else ("STOP_BREACH",),
    )
    return NewRecommendation(
        recommendation_id=RecommendationID(UUID(int=10)),
        recommendation_key=recommendation_key(source),
        content_digest=recommendation_content_digest(source),
        recommendation_input=source,
        generated_at=GENERATED_AT,
    )


def _row(value: NewRecommendation | None = None) -> dict[str, object]:
    recommendation = _new_recommendation() if value is None else value
    source = recommendation.recommendation_input
    plan = source.plan
    return {
        "recommendation_id": recommendation.recommendation_id.value,
        "recommendation_key": recommendation.recommendation_key,
        "content_digest": recommendation.content_digest,
        "feature_snapshot_id": source.feature_snapshot_id.value,
        "generator_code": source.generator_code,
        "generator_version": source.generator_version,
        "disposition": source.disposition.value,
        "currency": None if plan is None else plan.currency.code,
        "entry_price_low": None if plan is None else plan.entry_price_low.value,
        "entry_price_high": None if plan is None else plan.entry_price_high.value,
        "target_price": None if plan is None else plan.target_price.value,
        "stop_price": None if plan is None else plan.stop_price.value,
        "expected_holding_trading_days": (
            None if plan is None else plan.expected_holding_trading_days.value
        ),
        "upside_probability": None if plan is None else plan.upside_probability.value,
        "target_probability": None if plan is None else plan.target_probability.value,
        "stop_probability": None if plan is None else plan.stop_probability.value,
        "expected_value_rate": None if plan is None else plan.expected_value_rate.value,
        "reward_risk_ratio": None if plan is None else plan.reward_risk_ratio.value,
        "confidence": None if plan is None else plan.confidence.value,
        "valid_until": None if plan is None else plan.valid_until,
        "reason_codes": serialize_codes(source.reason_codes),
        "risk_codes": serialize_codes(source.risk_codes),
        "invalidation_codes": serialize_codes(source.invalidation_codes),
        "generated_at": recommendation.generated_at,
        "recorded_at": datetime(2026, 7, 28, 5, 0, 1, tzinfo=UTC),
    }


def test_table_columns_constraints_uniques_fk_and_indexes_are_exact() -> None:
    assert tuple(recommendations.c.keys()) == (
        "recommendation_id",
        "recommendation_key",
        "content_digest",
        "feature_snapshot_id",
        "generator_code",
        "generator_version",
        "disposition",
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
        "reason_codes",
        "risk_codes",
        "invalidation_codes",
        "generated_at",
        "recorded_at",
    )
    uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in recommendations.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert uniques == {
        ("recommendation_key",),
        ("feature_snapshot_id", "generator_code", "generator_version"),
    }
    foreign_keys = [
        constraint
        for constraint in recommendations.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert foreign_keys[0].ondelete == "NO ACTION"
    assert foreign_keys[0].referred_table.name == "feature_snapshots"
    assert (
        len(
            [
                constraint
                for constraint in recommendations.constraints
                if isinstance(constraint, CheckConstraint)
            ]
        )
        == 24
    )
    assert {index.name for index in recommendations.indexes} == {
        "ix_recommendations_feature_snapshot_id",
        "ix_recommendations_disposition_generated_at",
        "ix_recommendations_generator_generated_at",
        "ix_recommendations_generated_at",
    }


def test_mapping_round_trips_actionable_decimal_utc_and_sorted_json() -> None:
    mapped = map_recommendation(_row())

    assert mapped.recommendation_input.plan is not None
    assert mapped.recommendation_input.plan.entry_price_low.value.as_tuple().exponent == -2
    assert mapped.generated_at.tzinfo is UTC
    assert mapped.recorded_at.tzinfo is UTC
    assert mapped.recommendation_input.reason_codes == ("EXPECTED_VALUE_POSITIVE",)


def test_mapping_round_trips_non_actionable_null_plan() -> None:
    value = _new_recommendation(RecommendationDisposition.WATCH)

    mapped = map_recommendation(_row(value))

    assert mapped.recommendation_input.plan is None
    assert mapped.recommendation_input.risk_codes == ()
    assert mapped.recommendation_input.invalidation_codes == ()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("reason_codes", '{"secret":"value"}'),
        ("risk_codes", '["lowercase"]'),
        ("currency", "KRW"),
    ],
)
def test_invalid_stored_shape_is_redacted(column: str, value: object) -> None:
    row = _row()
    row[column] = value

    with pytest.raises(PersistenceMappingError) as captured:
        map_recommendation(row)

    assert "secret" not in str(captured.value)
    assert "lowercase" not in str(captured.value)


def test_repository_protocol_is_insert_only_with_precise_getters() -> None:
    methods = {
        name
        for name, value in getmembers(RecommendationRepository, isfunction)
        if not name.startswith("_")
    }
    assert methods == {
        "add",
        "get_by_id",
        "get_by_recommendation_key",
        "list_by_feature_snapshot_id",
    }
    assert not {"update", "delete", "upsert", "commit", "rollback"}.intersection(methods)


def test_repository_add_and_getters_use_only_caller_connection() -> None:
    connection = MagicMock()
    selected = MagicMock()
    selected.mappings.return_value.one_or_none.return_value = _row()
    connection.execute.side_effect = [MagicMock(), selected]
    repository = SqlAlchemyRecommendationRepository(cast(Connection, connection))

    stored = repository.add(_new_recommendation())

    assert stored.recommendation_id == RecommendationID(UUID(int=10))
    assert connection.execute.call_count == 2
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()

    for getter, argument in (
        ("get_by_id", RecommendationID(UUID(int=10))),
        ("get_by_recommendation_key", _new_recommendation().recommendation_key),
    ):
        selected_get = MagicMock()
        selected_get.mappings.return_value.one_or_none.return_value = _row()
        connection.execute.side_effect = None
        connection.execute.return_value = selected_get
        result = getattr(repository, getter)(argument)
        assert result is not None


def test_list_by_feature_snapshot_is_mapped_in_canonical_order() -> None:
    connection = MagicMock()
    selected = MagicMock()
    selected.mappings.return_value.all.return_value = [_row()]
    connection.execute.return_value = selected
    repository = SqlAlchemyRecommendationRepository(cast(Connection, connection))

    result = repository.list_by_feature_snapshot_id(FeatureSnapshotID(UUID(int=1)))

    assert len(result) == 1
    assert result[0].recommendation_input.feature_snapshot_id == FeatureSnapshotID(UUID(int=1))
