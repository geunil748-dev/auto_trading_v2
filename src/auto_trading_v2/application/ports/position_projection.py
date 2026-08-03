"""Repository boundaries used only by the canonical Position Projector."""

from typing import Protocol

from auto_trading_v2.application.contracts.position_projection import (
    NewPaperPosition,
    NewPositionEvent,
    PaperPositionBuyTransition,
    StoredPaperPosition,
    StoredPositionEvent,
)
from auto_trading_v2.domain.primitives import (
    Currency,
    FillID,
    PositionEventID,
    PositionID,
    StrategyID,
    Symbol,
)


class PaperPositionRepository(Protocol):
    def add(self, position: NewPaperPosition) -> StoredPaperPosition: ...

    def get(self, position_id: PositionID) -> StoredPaperPosition | None: ...

    def get_open_by_key(
        self,
        *,
        strategy_id: StrategyID,
        symbol: Symbol,
        currency: Currency,
    ) -> StoredPaperPosition | None: ...

    def transition_after_buy_fill(
        self,
        transition: PaperPositionBuyTransition,
    ) -> StoredPaperPosition: ...


class PositionEventRepository(Protocol):
    def add(self, event: NewPositionEvent) -> StoredPositionEvent: ...

    def get(self, position_event_id: PositionEventID) -> StoredPositionEvent | None: ...

    def get_by_fill_id(self, fill_id: FillID) -> StoredPositionEvent | None: ...

    def get_by_position_sequence(
        self,
        position_id: PositionID,
        sequence_no: int,
    ) -> StoredPositionEvent | None: ...
