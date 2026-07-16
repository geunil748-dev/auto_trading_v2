"""Atomic projection of one canonical BUY PaperFill into position state."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    NewPositionEvent,
    PaperPositionBuyTransition,
    PositionProjectionResult,
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.application.errors import (
    DuplicateRecordError,
    OptimisticConcurrencyError,
    PersistenceError,
    PersistenceMappingError,
    PersistenceNotFoundError,
)
from auto_trading_v2.application.ports.id_factory import (
    PositionEventIDFactory,
    PositionIDFactory,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from auto_trading_v2.application.position_projection_errors import (
    InvalidPositionFillError,
    PositionNotFoundDuringTransitionError,
    PositionProjectionConcurrencyError,
    PositionProjectionPersistenceError,
    PositionProjectionSourceError,
)
from auto_trading_v2.application.services.position_projection_source import (
    ProjectionSource,
    load_projection_source,
)
from auto_trading_v2.domain.position_projection import (
    PaperPositionStatus,
    PositionEventType,
    PositionProjectionValidationError,
    ProjectionOutcome,
    calculate_buy_position,
)
from auto_trading_v2.domain.primitives import FillID, Money, PositionID, Price, Quantity

_CONCURRENCY_CONSTRAINTS = {
    "ix_paper_positions_open_unique",
    "uq_position_events_position_sequence",
}
_SOURCE_ENTITIES = {
    "paper_order",
    "trade_intent",
    "strategy_decision",
    "candidate",
    "market_snapshot",
}


@dataclass(frozen=True, slots=True)
class PositionProjectorService:
    """Apply one canonical Fill at most once without accepting caller-derived values."""

    unit_of_work_factory: UnitOfWorkFactory
    position_id_factory: PositionIDFactory
    position_event_id_factory: PositionEventIDFactory

    def project_fill(self, fill_id: FillID) -> PositionProjectionResult:
        try:
            return self._project_once(fill_id)
        except DuplicateRecordError as exc:
            return self._resolve_duplicate(fill_id, exc)
        except PersistenceMappingError as exc:
            if exc.entity == "paper_fill":
                raise InvalidPositionFillError(fill_id, "invalid_stored_fill") from None
            if exc.entity in _SOURCE_ENTITIES:
                raise PositionProjectionSourceError(fill_id, "invalid_stored_source") from None
            raise PositionProjectionPersistenceError(fill_id, "invalid_stored_state") from None
        except PersistenceError as exc:
            raise PositionProjectionPersistenceError(
                fill_id,
                exc.constraint or exc.reason,
            ) from None

    def _project_once(self, fill_id: FillID) -> PositionProjectionResult:
        with self.unit_of_work_factory() as unit_of_work:
            existing_event = unit_of_work.position_events.get_by_fill_id(fill_id)
            if existing_event is not None:
                return _result(existing_event, ProjectionOutcome.ALREADY_APPLIED)
            source = load_projection_source(unit_of_work, fill_id)
            position = unit_of_work.paper_positions.get_open_by_key(
                strategy_id=source.decision.strategy_id,
                symbol=source.intent.symbol,
                currency=source.intent.currency,
            )
            if position is None:
                result = self._open_position(unit_of_work, source)
            else:
                result = self._increase_position(unit_of_work, source, position)
            unit_of_work.commit()
            return result

    def _open_position(
        self,
        unit_of_work: UnitOfWork,
        source: ProjectionSource,
    ) -> PositionProjectionResult:
        try:
            values = calculate_buy_position(
                fill_quantity=source.fill.quantity,
                fill_price=source.fill.price,
            )
        except PositionProjectionValidationError as exc:
            raise InvalidPositionFillError(source.fill.fill_id, "calculation_failed") from exc
        position_id = self.position_id_factory.new()
        zero_pnl = Money(Decimal("0"), source.intent.currency)
        position = NewPaperPosition(
            position_id=position_id,
            strategy_id=source.decision.strategy_id,
            symbol=source.intent.symbol,
            currency=source.intent.currency,
            status=PaperPositionStatus.OPEN,
            quantity=values.quantity,
            average_cost_price=values.average_price,
            realized_pnl=zero_pnl,
            opened_at=source.fill.executed_at,
            closed_at=None,
            version=1,
            updated_at=source.fill.executed_at,
        )
        unit_of_work.paper_positions.add(position)
        event = self._new_event(
            source=source,
            position_id=position_id,
            event_type=PositionEventType.OPENED,
            sequence_no=1,
            quantity_after=values.quantity,
            average_cost_after=values.average_price,
            realized_pnl_after=zero_pnl,
        )
        stored_event = unit_of_work.position_events.add(event)
        return _result(stored_event, ProjectionOutcome.APPLIED)

    def _increase_position(
        self,
        unit_of_work: UnitOfWork,
        source: ProjectionSource,
        position: StoredPaperPosition,
    ) -> PositionProjectionResult:
        if source.fill.executed_at < position.updated_at:
            raise InvalidPositionFillError(source.fill.fill_id, "fill_precedes_position")
        try:
            values = calculate_buy_position(
                current_quantity=position.quantity,
                current_average_price=position.average_cost_price,
                fill_quantity=source.fill.quantity,
                fill_price=source.fill.price,
            )
        except PositionProjectionValidationError as exc:
            raise InvalidPositionFillError(source.fill.fill_id, "calculation_failed") from exc
        event = self._new_event(
            source=source,
            position_id=position.position_id,
            event_type=PositionEventType.INCREASED,
            sequence_no=position.version + 1,
            quantity_after=values.quantity,
            average_cost_after=values.average_price,
            realized_pnl_after=position.realized_pnl,
        )
        stored_event = unit_of_work.position_events.add(event)
        transition = PaperPositionBuyTransition(
            position_id=position.position_id,
            expected_version=position.version,
            quantity=values.quantity,
            average_cost_price=values.average_price,
            updated_at=source.fill.executed_at,
        )
        try:
            unit_of_work.paper_positions.transition_after_buy_fill(transition)
        except PersistenceNotFoundError:
            raise PositionNotFoundDuringTransitionError(
                source.fill.fill_id,
                position.position_id,
            ) from None
        except OptimisticConcurrencyError:
            raise PositionProjectionConcurrencyError(source.fill.fill_id) from None
        return _result(stored_event, ProjectionOutcome.APPLIED)

    def _new_event(
        self,
        *,
        source: ProjectionSource,
        position_id: PositionID,
        event_type: PositionEventType,
        sequence_no: int,
        quantity_after: Quantity,
        average_cost_after: Price,
        realized_pnl_after: Money,
    ) -> NewPositionEvent:
        return NewPositionEvent(
            position_event_id=self.position_event_id_factory.new(),
            position_id=position_id,
            fill_id=source.fill.fill_id,
            sequence_no=sequence_no,
            event_type=event_type,
            quantity_delta=source.fill.quantity,
            quantity_after=quantity_after,
            average_cost_after=average_cost_after,
            realized_pnl_delta=Money(Decimal("0"), source.intent.currency),
            realized_pnl_after=realized_pnl_after,
            occurred_at=source.fill.executed_at,
        )

    def _resolve_duplicate(
        self,
        fill_id: FillID,
        error: DuplicateRecordError,
    ) -> PositionProjectionResult:
        try:
            with self.unit_of_work_factory() as unit_of_work:
                event = unit_of_work.position_events.get_by_fill_id(fill_id)
        except PersistenceError as exc:
            raise PositionProjectionPersistenceError(
                fill_id,
                exc.constraint or exc.reason,
            ) from None
        if event is not None:
            return _result(event, ProjectionOutcome.ALREADY_APPLIED)
        if error.constraint in _CONCURRENCY_CONSTRAINTS:
            raise PositionProjectionConcurrencyError(
                fill_id,
                error.constraint or "projection_race",
            ) from None
        raise PositionProjectionPersistenceError(
            fill_id,
            error.constraint or error.reason,
        ) from None


def _result(
    event: StoredPositionEvent,
    outcome: ProjectionOutcome,
) -> PositionProjectionResult:
    return PositionProjectionResult(
        outcome=outcome,
        fill_id=event.fill_id,
        position_id=event.position_id,
        position_event_id=event.position_event_id,
        event_type=event.event_type,
        quantity=event.quantity_after,
        average_cost_price=event.average_cost_after,
        position_version=event.sequence_no,
    )
