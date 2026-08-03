"""Payload-safe failures for deterministic position exit decisions."""

from __future__ import annotations

import re

from auto_trading_v2.domain.primitives import Currency, MarketSnapshotID, PositionID

_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_]{1,128}$")


def _safe_label(value: str, fallback: str) -> str:
    return value if isinstance(value, str) and _SAFE_LABEL.fullmatch(value) else fallback


class PositionExitPositionNotFoundError(RuntimeError):
    """The requested canonical PaperPosition does not exist."""

    def __init__(self, position_id: PositionID) -> None:
        self.position_id = position_id
        super().__init__(f"position exit source missing: {position_id.serialize()}")


class PositionExitSnapshotNotFoundError(RuntimeError):
    """The requested canonical MarketSnapshot does not exist."""

    def __init__(self, market_snapshot_id: MarketSnapshotID) -> None:
        self.market_snapshot_id = market_snapshot_id
        super().__init__(f"position exit snapshot missing: {market_snapshot_id.serialize()}")


class PositionExitSourceError(RuntimeError):
    """Canonical source data cannot safely drive an exit decision."""

    def __init__(
        self,
        position_id: PositionID,
        market_snapshot_id: MarketSnapshotID,
        reason: str,
    ) -> None:
        self.position_id = position_id
        self.market_snapshot_id = market_snapshot_id
        self.reason = _safe_label(reason, "invalid_source")
        super().__init__(
            "position exit source invalid: "
            f"{position_id.serialize()}/{market_snapshot_id.serialize()}/{self.reason}"
        )


class UnsupportedPositionExitCurrencyError(RuntimeError):
    """The initial position exit policy accepts USD positions only."""

    def __init__(self, position_id: PositionID, currency: Currency) -> None:
        self.position_id = position_id
        self.currency = currency
        super().__init__(
            f"position exit currency unsupported: {position_id.serialize()}/{currency.code}"
        )


class PositionExitPersistenceError(RuntimeError):
    """An unrelated persistence failure prevented an exit decision."""

    def __init__(self, position_id: PositionID, category: str) -> None:
        self.position_id = position_id
        self.category = _safe_label(category, "persistence_failure")
        super().__init__(
            f"position exit persistence failure: {position_id.serialize()}/{self.category}"
        )
