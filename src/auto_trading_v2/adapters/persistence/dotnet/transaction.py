"""One-shot SqlTransaction lifecycle without repository ownership."""

from __future__ import annotations

from contextlib import suppress
from enum import StrEnum
from types import TracebackType
from typing import Any

from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetTransactionStateError,
    safe_persistence_error,
)


class DotNetTransactionState(StrEnum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    FINISHED = "FINISHED"


class DotNetTransaction:
    """Own one transaction while leaving connection ownership to the factory."""

    def __init__(self, connection: object) -> None:
        self._connection = connection
        self._transaction: object | None = None
        self._state = DotNetTransactionState.NEW

    @property
    def state(self) -> DotNetTransactionState:
        return self._state

    @property
    def raw_transaction(self) -> object:
        self._ensure_active("transaction_access")
        if self._transaction is None:
            raise DotNetTransactionStateError("transaction_access", self._state.value)
        return self._transaction

    def __enter__(self) -> DotNetTransaction:
        if self._state is not DotNetTransactionState.NEW:
            raise DotNetTransactionStateError("begin", self._state.value)
        dynamic: Any = self._connection
        try:
            self._transaction = dynamic.BeginTransaction()
        except Exception as exc:
            self._state = DotNetTransactionState.FINISHED
            raise safe_persistence_error(exc, operation="begin") from None
        self._state = DotNetTransactionState.ACTIVE
        return self

    def commit(self) -> None:
        transaction = self._active_transaction("commit")
        dynamic: Any = transaction
        try:
            dynamic.Commit()
        except Exception as exc:
            with suppress(Exception):
                dynamic.Rollback()
            self._state = DotNetTransactionState.FINISHED
            raise safe_persistence_error(exc, operation="commit") from None
        self._state = DotNetTransactionState.COMMITTED

    def rollback(self) -> None:
        transaction = self._active_transaction("rollback")
        dynamic: Any = transaction
        try:
            dynamic.Rollback()
        except Exception as exc:
            self._state = DotNetTransactionState.FINISHED
            raise safe_persistence_error(exc, operation="rollback") from None
        self._state = DotNetTransactionState.ROLLED_BACK

    def dispose(self) -> None:
        transaction = self._transaction
        self._transaction = None
        if transaction is None:
            self._state = DotNetTransactionState.FINISHED
            return
        dynamic: Any = transaction
        try:
            dynamic.Dispose()
        except Exception as exc:
            self._state = DotNetTransactionState.FINISHED
            raise safe_persistence_error(exc, operation="dispose_transaction") from None
        self._state = DotNetTransactionState.FINISHED

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        rollback_error: BaseException | None = None
        if self._state is DotNetTransactionState.ACTIVE:
            try:
                self.rollback()
            except BaseException as caught:
                if exc is None:
                    rollback_error = caught
        try:
            self.dispose()
        except BaseException as caught:
            if exc is None and rollback_error is None:
                rollback_error = caught
        if rollback_error is not None:
            raise rollback_error

    def _ensure_active(self, operation: str) -> None:
        if self._state is not DotNetTransactionState.ACTIVE:
            raise DotNetTransactionStateError(operation, self._state.value)

    def _active_transaction(self, operation: str) -> object:
        self._ensure_active(operation)
        if self._transaction is None:
            raise DotNetTransactionStateError(operation, self._state.value)
        return self._transaction
