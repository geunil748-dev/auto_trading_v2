"""SQLAlchemy Core Unit of Work with an explicit one-shot lifecycle."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum, auto
from types import TracebackType

from sqlalchemy import Connection, Engine
from sqlalchemy.engine import RootTransaction
from sqlalchemy.exc import SQLAlchemyError

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyCandidateRepository,
    SqlAlchemyFilterEvaluationRepository,
    SqlAlchemyMarketSnapshotRepository,
)
from auto_trading_v2.application.errors import TransactionStateError


class _State(Enum):
    NEW = auto()
    ACTIVE = auto()
    COMMITTED = auto()
    ROLLED_BACK = auto()
    FINISHED = auto()


class SqlAlchemyUnitOfWork:
    """Own one connection and root transaction for exactly one context entry."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._state = _State.NEW
        self._rollback_only = False
        self._connection: Connection | None = None
        self._transaction: RootTransaction | None = None
        self._market_snapshots: SqlAlchemyMarketSnapshotRepository | None = None
        self._candidates: SqlAlchemyCandidateRepository | None = None
        self._filter_evaluations: SqlAlchemyFilterEvaluationRepository | None = None

    @property
    def market_snapshots(self) -> SqlAlchemyMarketSnapshotRepository:
        self._ensure_repository_operation()
        if self._market_snapshots is None:
            raise TransactionStateError("repository_access")
        return self._market_snapshots

    @property
    def candidates(self) -> SqlAlchemyCandidateRepository:
        self._ensure_repository_operation()
        if self._candidates is None:
            raise TransactionStateError("repository_access")
        return self._candidates

    @property
    def filter_evaluations(self) -> SqlAlchemyFilterEvaluationRepository:
        self._ensure_repository_operation()
        if self._filter_evaluations is None:
            raise TransactionStateError("repository_access")
        return self._filter_evaluations

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        if self._state is not _State.NEW:
            raise TransactionStateError("enter", "instance_reuse_forbidden")
        try:
            connection = self._engine.connect()
            try:
                transaction = connection.begin()
            except SQLAlchemyError:
                connection.close()
                raise
        except SQLAlchemyError as exc:
            self._state = _State.FINISHED
            raise translate_persistence_error(
                exc, entity="unit_of_work", operation="begin"
            ) from None
        self._connection = connection
        self._transaction = transaction
        self._state = _State.ACTIVE
        repository_args = (connection, self._ensure_repository_operation, self._mark_failed)
        self._market_snapshots = SqlAlchemyMarketSnapshotRepository(*repository_args)
        self._candidates = SqlAlchemyCandidateRepository(*repository_args)
        self._filter_evaluations = SqlAlchemyFilterEvaluationRepository(*repository_args)
        return self

    def commit(self) -> None:
        self._ensure_active("commit")
        if self._rollback_only:
            self._rollback_transaction()
            raise TransactionStateError("commit", "transaction_failed")
        transaction = self._require_transaction("commit")
        try:
            transaction.commit()
        except SQLAlchemyError as exc:
            self._rollback_after_failure()
            raise translate_persistence_error(
                exc, entity="unit_of_work", operation="commit"
            ) from None
        self._state = _State.COMMITTED

    def rollback(self) -> None:
        self._ensure_active("rollback")
        self._rollback_transaction()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        failure: BaseException | None = None
        try:
            if self._state is _State.ACTIVE:
                try:
                    self._rollback_transaction()
                except BaseException as rollback_error:
                    if exc is None:
                        failure = rollback_error
        finally:
            connection = self._connection
            self._connection = None
            if connection is not None:
                try:
                    connection.close()
                except SQLAlchemyError as close_error:
                    if exc is None and failure is None:
                        failure = translate_persistence_error(
                            close_error, entity="unit_of_work", operation="close"
                        )
            if self._state not in {_State.COMMITTED, _State.ROLLED_BACK}:
                self._state = _State.FINISHED
        if failure is not None:
            raise failure

    def _ensure_active(self, operation: str) -> None:
        if self._state is not _State.ACTIVE:
            raise TransactionStateError(operation)

    def _ensure_repository_operation(self) -> None:
        self._ensure_active("repository_operation")
        if self._rollback_only:
            raise TransactionStateError("repository_operation", "transaction_failed")

    def _mark_failed(self) -> None:
        self._rollback_only = True

    def _require_transaction(self, operation: str) -> RootTransaction:
        if self._transaction is None:
            raise TransactionStateError(operation)
        return self._transaction

    def _rollback_transaction(self) -> None:
        transaction = self._require_transaction("rollback")
        try:
            transaction.rollback()
        except SQLAlchemyError as exc:
            self._state = _State.FINISHED
            raise translate_persistence_error(
                exc, entity="unit_of_work", operation="rollback"
            ) from None
        self._state = _State.ROLLED_BACK

    def _rollback_after_failure(self) -> None:
        transaction = self._transaction
        if transaction is not None and transaction.is_active:
            with suppress(SQLAlchemyError):
                transaction.rollback()
        self._state = _State.FINISHED


@dataclass(frozen=True, slots=True)
class SqlAlchemyUnitOfWorkFactory:
    """Create a fresh one-shot Unit of Work for each application operation."""

    engine: Engine = field(repr=False)

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.engine)
