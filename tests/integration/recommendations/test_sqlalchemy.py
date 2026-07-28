import pytest

from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.recommendations import RecommendationCreationOutcome
from auto_trading_v2.application.recommendation_errors import RecommendationConflictError
from auto_trading_v2.domain.recommendations import RecommendationDisposition
from tests.integration.recommendations.helpers import (
    command,
    creation_service,
    new_recommendation,
    persist_snapshot,
)

pytestmark = pytest.mark.integration


def test_sqlalchemy_actionable_retry_getters_list_and_conflict(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    snapshot = persist_snapshot(sqlalchemy_uow_factory, 101)
    source = command(snapshot, 101)
    service = creation_service(sqlalchemy_uow_factory, snapshot, 101)

    created = service.create(source)
    retried = service.create(source)

    assert created.outcome is RecommendationCreationOutcome.CREATED
    assert retried.outcome is RecommendationCreationOutcome.ALREADY_EXISTS
    assert retried.recommendation == created.recommendation
    with sqlalchemy_uow_factory() as unit_of_work:
        assert (
            unit_of_work.recommendations.get_by_id(created.recommendation.recommendation_id)
            == created.recommendation
        )
        assert (
            unit_of_work.recommendations.get_by_recommendation_key(
                created.recommendation.recommendation_key
            )
            == created.recommendation
        )
        assert unit_of_work.recommendations.list_by_feature_snapshot_id(
            snapshot.feature_snapshot_id
        ) == (created.recommendation,)

    conflicting = command(snapshot, 101, reason_codes=("OTHER_REASON",))
    with pytest.raises(RecommendationConflictError):
        service.create(conflicting)


def test_sqlalchemy_non_actionable_null_shape_and_implicit_rollback(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> None:
    snapshot = persist_snapshot(sqlalchemy_uow_factory, 102)
    source = command(
        snapshot,
        102,
        disposition=RecommendationDisposition.DATA_INSUFFICIENT,
        reason_codes=("SOURCE_INSUFFICIENT",),
    )
    service = creation_service(sqlalchemy_uow_factory, snapshot, 102)

    created = service.create(source)

    assert created.recommendation.recommendation_input.plan is None
    rollback_source = command(snapshot, 103)
    pending = new_recommendation(rollback_source, snapshot, 103)
    with sqlalchemy_uow_factory() as unit_of_work:
        unit_of_work.recommendations.add(pending)
    with sqlalchemy_uow_factory() as unit_of_work:
        assert unit_of_work.recommendations.get_by_id(pending.recommendation_id) is None
