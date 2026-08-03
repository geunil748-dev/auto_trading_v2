import pytest

from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
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


def test_dotnet_actionable_non_actionable_retry_read_and_conflict(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    snapshot = persist_snapshot(dotnet_uow_factory, 111)
    source = command(snapshot, 111)
    service = creation_service(dotnet_uow_factory, snapshot, 111)

    created = service.create(source)
    retried = service.create(source)

    assert created.outcome is RecommendationCreationOutcome.CREATED
    assert retried.outcome is RecommendationCreationOutcome.ALREADY_EXISTS
    with dotnet_uow_factory() as unit_of_work:
        assert (
            unit_of_work.recommendations.get_by_id(created.recommendation.recommendation_id)
            == created.recommendation
        )
        assert unit_of_work.recommendations.list_by_feature_snapshot_id(
            snapshot.feature_snapshot_id
        ) == (created.recommendation,)
    with pytest.raises(RecommendationConflictError):
        service.create(command(snapshot, 111, reason_codes=("OTHER_REASON",)))

    other_snapshot = persist_snapshot(dotnet_uow_factory, 112)
    non_actionable = creation_service(dotnet_uow_factory, other_snapshot, 112).create(
        command(
            other_snapshot,
            112,
            disposition=RecommendationDisposition.WATCH,
            reason_codes=("WATCH_ONLY",),
        )
    )
    assert non_actionable.recommendation.recommendation_input.plan is None


def test_dotnet_implicit_rollback_has_no_visible_residue(
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    snapshot = persist_snapshot(dotnet_uow_factory, 113)
    source = command(snapshot, 113)
    pending = new_recommendation(source, snapshot, 113)

    with dotnet_uow_factory() as unit_of_work:
        unit_of_work.recommendations.add(pending)

    with dotnet_uow_factory() as unit_of_work:
        assert unit_of_work.recommendations.get_by_id(pending.recommendation_id) is None
