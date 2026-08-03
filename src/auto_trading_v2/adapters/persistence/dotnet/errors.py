"""Secret-safe DotNet persistence error categories and boundaries."""

from __future__ import annotations

import re
from enum import StrEnum

from auto_trading_v2.application.errors import (
    CheckConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
    PersistenceError,
    PersistenceUnavailableError,
)


class DotNetErrorCategory(StrEnum):
    UNIQUE_VIOLATION = "UNIQUE_VIOLATION"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    FOREIGN_KEY_VIOLATION = "FOREIGN_KEY_VIOLATION"
    CHECK_CONSTRAINT_VIOLATION = "CHECK_CONSTRAINT_VIOLATION"
    DEADLOCK = "DEADLOCK"
    TIMEOUT = "TIMEOUT"
    AUTHENTICATION = "AUTHENTICATION"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    UNKNOWN = "UNKNOWN"


class DotNetRuntimeError(RuntimeError):
    """Report only the failed import/runtime stage and exception class."""

    def __init__(self, stage: str, exception_class: str) -> None:
        self.stage = stage
        self.exception_class = exception_class
        super().__init__(f"DotNet runtime unavailable at {stage} ({exception_class})")


class DotNetPersistenceError(RuntimeError):
    """Sanitized persistence failure without a raw SqlException message."""

    def __init__(
        self,
        *,
        operation: str,
        category: DotNetErrorCategory,
        number: int | None = None,
        constraint: str | None = None,
    ) -> None:
        self.provider = "dotnet"
        self.operation = operation
        self.category = category
        self.number = number
        self.constraint = constraint
        number_text = "known" if number is not None else "unavailable"
        super().__init__(
            f"DotNet persistence {operation} failed: {category.value} (number={number_text})"
        )


class DotNetTransactionStateError(RuntimeError):
    def __init__(self, operation: str, state: str) -> None:
        self.operation = operation
        self.state = state
        super().__init__(f"DotNet transaction operation {operation} is invalid in state {state}")


class DotNetParameterError(ValueError):
    """Value-free invalid parameter contract error."""


class DotNetResultConversionError(ValueError):
    """Value-free unsupported result conversion error."""


_NUMBER_CATEGORIES = {
    -2: DotNetErrorCategory.TIMEOUT,
    547: DotNetErrorCategory.CONSTRAINT_VIOLATION,
    1205: DotNetErrorCategory.DEADLOCK,
    2601: DotNetErrorCategory.UNIQUE_VIOLATION,
    2627: DotNetErrorCategory.UNIQUE_VIOLATION,
    4060: DotNetErrorCategory.DATABASE_UNAVAILABLE,
    18456: DotNetErrorCategory.AUTHENTICATION,
}


def classify_sql_number(number: int | None) -> DotNetErrorCategory:
    """Classify only explicitly known SqlException numbers."""

    if number is None:
        return DotNetErrorCategory.UNKNOWN
    return _NUMBER_CATEGORIES.get(number, DotNetErrorCategory.UNKNOWN)


def safe_persistence_error(exc: BaseException, *, operation: str) -> DotNetPersistenceError:
    """Discard raw exception text and retain only a safe numeric classification."""

    raw_number = getattr(exc, "Number", None)
    number = raw_number if isinstance(raw_number, int) else None
    internal_text = str(exc)
    match = re.search(r"\b((?:fk|ck|uq|ix)_[A-Za-z0-9_]{1,120})\b", internal_text)
    constraint = None if match is None else match.group(1).casefold()
    category = classify_sql_number(number)
    if number == 547:
        folded = internal_text.casefold()
        if (constraint and constraint.startswith("fk_")) or "foreign key" in folded:
            category = DotNetErrorCategory.FOREIGN_KEY_VIOLATION
        elif (constraint and constraint.startswith("ck_")) or "check constraint" in folded:
            category = DotNetErrorCategory.CHECK_CONSTRAINT_VIOLATION
    return DotNetPersistenceError(
        operation=operation,
        category=category,
        number=number,
        constraint=constraint,
    )


def translate_dotnet_error(
    error: DotNetPersistenceError,
    *,
    entity: str,
    operation: str,
) -> PersistenceError:
    """Translate categorical DotNet failures into the existing application contract."""

    if error.category is DotNetErrorCategory.UNIQUE_VIOLATION:
        return DuplicateRecordError(
            entity=entity,
            operation=operation,
            reason="duplicate_record",
            constraint=error.constraint,
        )
    if error.category is DotNetErrorCategory.FOREIGN_KEY_VIOLATION:
        return ForeignKeyViolationError(
            entity=entity,
            operation=operation,
            reason="foreign_key_violation",
            constraint=error.constraint,
        )
    if error.category is DotNetErrorCategory.CHECK_CONSTRAINT_VIOLATION:
        return CheckConstraintViolationError(
            entity=entity,
            operation=operation,
            reason="check_constraint_violation",
            constraint=error.constraint,
        )
    if error.category in {
        DotNetErrorCategory.AUTHENTICATION,
        DotNetErrorCategory.CONNECTION_FAILURE,
        DotNetErrorCategory.DATABASE_UNAVAILABLE,
    }:
        return PersistenceUnavailableError(
            entity=entity,
            operation=operation,
            reason="database_unavailable",
        )
    reason = {
        DotNetErrorCategory.CONSTRAINT_VIOLATION: "integrity_violation",
        DotNetErrorCategory.DEADLOCK: "deadlock",
        DotNetErrorCategory.TIMEOUT: "timeout",
    }.get(error.category, "operation_failed")
    return PersistenceError(entity=entity, operation=operation, reason=reason)
