import pytest

from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.position_projection_errors import (
    PositionProjectionPersistenceError,
)

from .position_projector_fakes import FILL_ID, FakeUnitOfWork
from .test_position_projector_service import service_for


def test_invalid_stored_position_event_is_persistence_not_source_error() -> None:
    unit_of_work = FakeUnitOfWork()

    def invalid_event(fill_id: object) -> None:
        raise PersistenceMappingError("position_event")

    unit_of_work.position_events.get_by_fill_id = invalid_event  # type: ignore[method-assign]
    service, _, _, _ = service_for(unit_of_work)

    with pytest.raises(PositionProjectionPersistenceError, match="invalid_stored_state"):
        service.project_fill(FILL_ID)
