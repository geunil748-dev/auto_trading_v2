"""Payload-safe failures for one canonical Fill projection."""

from __future__ import annotations

import re

from auto_trading_v2.domain.primitives import FillID, PositionID
from auto_trading_v2.domain.trade_intents import TradeSide

_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_]{1,128}$")


def _safe_label(value: str, fallback: str) -> str:
    return value if isinstance(value, str) and _SAFE_LABEL.fullmatch(value) else fallback


class PositionFillNotFoundError(RuntimeError):
    """The requested canonical PaperFill does not exist."""

    def __init__(self, fill_id: FillID) -> None:
        self.fill_id = fill_id
        super().__init__(f"position projection fill not found: {fill_id.serialize()}")


class PositionProjectionSourceError(RuntimeError):
    """The canonical source chain cannot safely identify a BUY position."""

    def __init__(self, fill_id: FillID, reason: str) -> None:
        self.fill_id = fill_id
        self.reason = _safe_label(reason, "invalid_source")
        super().__init__(f"position projection source invalid: {fill_id.serialize()}/{self.reason}")


class UnsupportedPositionFillSideError(RuntimeError):
    """The projector currently accepts BUY Fill sources only."""

    def __init__(self, fill_id: FillID, side: TradeSide) -> None:
        self.fill_id = fill_id
        self.side = side
        super().__init__(f"unsupported position fill side: {fill_id.serialize()}/{side.value}")


class InvalidPositionFillError(RuntimeError):
    """The canonical Fill data cannot produce a valid position change."""

    def __init__(self, fill_id: FillID, reason: str) -> None:
        self.fill_id = fill_id
        self.reason = _safe_label(reason, "invalid_fill")
        super().__init__(f"invalid position fill: {fill_id.serialize()}/{self.reason}")


class PositionNotFoundDuringTransitionError(RuntimeError):
    """A planned update lost its canonical PaperPosition target."""

    def __init__(self, fill_id: FillID, position_id: PositionID) -> None:
        self.fill_id = fill_id
        self.position_id = position_id
        super().__init__(
            f"position missing during projection: {fill_id.serialize()}/{position_id.serialize()}"
        )


class PositionProjectionConcurrencyError(RuntimeError):
    """A concurrent projection changed the OPEN position or event sequence."""

    def __init__(self, fill_id: FillID, category: str = "stale_position") -> None:
        self.fill_id = fill_id
        self.category = _safe_label(category, "concurrency_conflict")
        super().__init__(
            f"position projection concurrency conflict: {fill_id.serialize()}/{self.category}"
        )


class PositionProjectionPersistenceError(RuntimeError):
    """An unrelated persistence constraint or database operation failed."""

    def __init__(self, fill_id: FillID, category: str) -> None:
        self.fill_id = fill_id
        self.category = _safe_label(category, "persistence_failure")
        super().__init__(
            f"position projection persistence failure: {fill_id.serialize()}/{self.category}"
        )
