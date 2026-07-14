"""Credential- and payload-safe persistence exception hierarchy."""

from __future__ import annotations

import re

from auto_trading_v2.domain.filtering.models import FilterSetName
from auto_trading_v2.domain.primitives import CandidateID, MarketSnapshotID

_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_]{1,128}$")


def _safe_label(value: str, fallback: str) -> str:
    return value if isinstance(value, str) and _SAFE_LABEL.fullmatch(value) else fallback


class PersistenceError(RuntimeError):
    """Base persistence failure containing only safe categorical context."""

    def __init__(
        self,
        *,
        entity: str,
        operation: str,
        reason: str = "operation_failed",
        constraint: str | None = None,
    ) -> None:
        self.entity = _safe_label(entity, "record")
        self.operation = _safe_label(operation, "operation")
        self.reason = _safe_label(reason, "operation_failed")
        self.constraint = (
            None if constraint is None else _safe_label(constraint, "unknown_constraint")
        )
        message = f"persistence {self.operation} failed for {self.entity}: {self.reason}"
        if self.constraint is not None:
            message += f" ({self.constraint})"
        super().__init__(message)


class PersistenceUnavailableError(PersistenceError):
    """Database connectivity or availability failure."""


class DuplicateRecordError(PersistenceError):
    """Database uniqueness violation."""


class ForeignKeyViolationError(PersistenceError):
    """Database referential-integrity violation."""


class CheckConstraintViolationError(PersistenceError):
    """Database check-constraint violation."""


class TransactionStateError(PersistenceError):
    """Invalid Unit of Work lifecycle transition."""

    def __init__(self, operation: str, reason: str = "invalid_transaction_state") -> None:
        super().__init__(entity="unit_of_work", operation=operation, reason=reason)


class PersistenceMappingError(PersistenceError):
    """Stored data could not be mapped to an application contract."""

    def __init__(self, entity: str, operation: str = "map") -> None:
        super().__init__(entity=entity, operation=operation, reason="invalid_stored_data")


class CandidateNotFoundError(RuntimeError):
    """The requested canonical candidate does not exist."""

    def __init__(self, candidate_id: CandidateID) -> None:
        self.candidate_id = candidate_id
        super().__init__(f"candidate not found: {candidate_id.serialize()}")


class MarketSnapshotNotFoundError(RuntimeError):
    """The candidate references no readable canonical market snapshot."""

    def __init__(self, market_snapshot_id: MarketSnapshotID) -> None:
        self.market_snapshot_id = market_snapshot_id
        super().__init__(f"market snapshot not found: {market_snapshot_id.serialize()}")


class FilterEvaluationConflictError(RuntimeError):
    """A versioned filter evaluation already exists."""

    def __init__(self, filter_set_name: FilterSetName) -> None:
        self.filter_set_name = filter_set_name
        super().__init__(f"filter evaluation conflict: {filter_set_name.value}")
