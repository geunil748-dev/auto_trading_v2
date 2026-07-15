"""Canonical PaperFill repository boundary."""

from collections.abc import Sequence
from typing import Protocol

from auto_trading_v2.application.contracts.paper_fills import NewPaperFill, StoredPaperFill
from auto_trading_v2.domain.primitives import FillID, OrderID


class PaperFillRepository(Protocol):
    def add(self, paper_fill: NewPaperFill) -> StoredPaperFill: ...

    def get(self, fill_id: FillID) -> StoredPaperFill | None: ...

    def get_by_execution_key(self, execution_key: str) -> StoredPaperFill | None: ...

    def get_by_order_sequence(
        self, *, order_id: OrderID, fill_sequence: int
    ) -> StoredPaperFill | None: ...

    def list_by_order(self, order_id: OrderID) -> Sequence[StoredPaperFill]: ...
