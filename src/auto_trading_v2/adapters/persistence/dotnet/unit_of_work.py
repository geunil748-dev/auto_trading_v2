from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from types import TracebackType
from typing import Any, TypeVar, cast

from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.dotnet.commands import DotNetCommandExecutor
from auto_trading_v2.adapters.persistence.dotnet.connection import DotNetConnectionFactory
from auto_trading_v2.adapters.persistence.dotnet.core_adapter import DotNetCoreConnection
from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetPersistenceError,
    safe_persistence_error,
    translate_dotnet_error,
)
from auto_trading_v2.adapters.persistence.dotnet.prediction_unit_of_work import (
    DotNetPredictionUnitOfWorkMixin,
)
from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetCandidateRepository,
    DotNetDailyFeaturePipelineRunRepository,
    DotNetDailyMarketBarRepository,
    DotNetFeatureSnapshotRepository,
    DotNetFilterEvaluationRepository,
    DotNetMarketSnapshotRepository,
    DotNetPaperFillRepository,
    DotNetPaperOrderRepository,
    DotNetPaperPositionRepository,
    DotNetPositionEventRepository,
    DotNetRecommendationRepository,
    DotNetStrategyDecisionRepository,
    DotNetTradeIntentRepository,
    DotNetUniverseSnapshotRepository,
)
from auto_trading_v2.adapters.persistence.dotnet.transaction import (
    DotNetTransaction,
    DotNetTransactionState,
)
from auto_trading_v2.application.errors import TransactionStateError


class _State(Enum):
    NEW = auto()
    ACTIVE = auto()
    COMMITTED = auto()
    ROLLED_BACK = auto()
    FINISHED = auto()


_Repository = TypeVar("_Repository")


class DotNetUnitOfWork(DotNetPredictionUnitOfWorkMixin):
    def __init__(
        self,
        connection_factory: DotNetConnectionFactory,
        executor: DotNetCommandExecutor | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._executor = DotNetCommandExecutor() if executor is None else executor
        self._state = _State.NEW
        self._rollback_only = False
        self._connection: object | None = None
        self._transaction: DotNetTransaction | None = None
        self._daily_market_bars: DotNetDailyMarketBarRepository | None = None
        self._feature_snapshots: DotNetFeatureSnapshotRepository | None = None
        self._universe_snapshots: DotNetUniverseSnapshotRepository | None = None
        self._daily_feature_pipeline_runs: DotNetDailyFeaturePipelineRunRepository | None = None
        self._initialize_prediction_repository_slots()
        self._recommendations: DotNetRecommendationRepository | None = None
        self._market_snapshots: DotNetMarketSnapshotRepository | None = None
        self._candidates: DotNetCandidateRepository | None = None
        self._filter_evaluations: DotNetFilterEvaluationRepository | None = None
        self._strategy_decisions: DotNetStrategyDecisionRepository | None = None
        self._trade_intents: DotNetTradeIntentRepository | None = None
        self._paper_orders: DotNetPaperOrderRepository | None = None
        self._paper_fills: DotNetPaperFillRepository | None = None
        self._paper_positions: DotNetPaperPositionRepository | None = None
        self._position_events: DotNetPositionEventRepository | None = None

    @property
    def daily_market_bars(self) -> DotNetDailyMarketBarRepository:
        return self._repository(self._daily_market_bars)

    @property
    def feature_snapshots(self) -> DotNetFeatureSnapshotRepository:
        return self._repository(self._feature_snapshots)

    @property
    def universe_snapshots(self) -> DotNetUniverseSnapshotRepository:
        return self._repository(self._universe_snapshots)

    @property
    def daily_feature_pipeline_runs(self) -> DotNetDailyFeaturePipelineRunRepository:
        return self._repository(self._daily_feature_pipeline_runs)

    @property
    def recommendations(self) -> DotNetRecommendationRepository:
        return self._repository(self._recommendations)

    @property
    def market_snapshots(self) -> DotNetMarketSnapshotRepository:
        return self._repository(self._market_snapshots)

    @property
    def candidates(self) -> DotNetCandidateRepository:
        return self._repository(self._candidates)

    @property
    def filter_evaluations(self) -> DotNetFilterEvaluationRepository:
        return self._repository(self._filter_evaluations)

    @property
    def strategy_decisions(self) -> DotNetStrategyDecisionRepository:
        return self._repository(self._strategy_decisions)

    @property
    def trade_intents(self) -> DotNetTradeIntentRepository:
        return self._repository(self._trade_intents)

    @property
    def paper_orders(self) -> DotNetPaperOrderRepository:
        return self._repository(self._paper_orders)

    @property
    def paper_fills(self) -> DotNetPaperFillRepository:
        return self._repository(self._paper_fills)

    @property
    def paper_positions(self) -> DotNetPaperPositionRepository:
        return self._repository(self._paper_positions)

    @property
    def position_events(self) -> DotNetPositionEventRepository:
        return self._repository(self._position_events)

    def __enter__(self) -> DotNetUnitOfWork:
        if self._state is not _State.NEW:
            raise TransactionStateError("enter", "instance_reuse_forbidden")
        try:
            connection = self._connection_factory.open_connection()
            transaction = DotNetTransaction(connection)
            transaction.__enter__()
        except DotNetPersistenceError as exc:
            self._state = _State.FINISHED
            if "connection" in locals():
                self._close_connection(connection)
            raise translate_dotnet_error(exc, entity="unit_of_work", operation="begin") from None
        self._connection = connection
        self._transaction = transaction
        self._state = _State.ACTIVE
        core = DotNetCoreConnection(connection, transaction.raw_transaction, self._executor)
        repository_args = (
            cast(Connection, core),
            self._ensure_repository_operation,
            self._mark_failed,
        )
        self._daily_market_bars = DotNetDailyMarketBarRepository(*repository_args)
        self._feature_snapshots = DotNetFeatureSnapshotRepository(*repository_args)
        self._universe_snapshots = DotNetUniverseSnapshotRepository(*repository_args)
        self._daily_feature_pipeline_runs = DotNetDailyFeaturePipelineRunRepository(
            *repository_args
        )
        self._bind_prediction_repositories(repository_args)
        self._recommendations = DotNetRecommendationRepository(*repository_args)
        self._market_snapshots = DotNetMarketSnapshotRepository(*repository_args)
        self._candidates = DotNetCandidateRepository(*repository_args)
        self._filter_evaluations = DotNetFilterEvaluationRepository(*repository_args)
        self._strategy_decisions = DotNetStrategyDecisionRepository(*repository_args)
        self._trade_intents = DotNetTradeIntentRepository(*repository_args)
        self._paper_orders = DotNetPaperOrderRepository(*repository_args)
        self._paper_fills = DotNetPaperFillRepository(*repository_args)
        self._paper_positions = DotNetPaperPositionRepository(*repository_args)
        self._position_events = DotNetPositionEventRepository(*repository_args)
        return self

    def commit(self) -> None:
        self._ensure_active("commit")
        if self._rollback_only:
            self._rollback_transaction()
            raise TransactionStateError("commit", "transaction_failed")
        transaction = self._require_transaction("commit")
        try:
            transaction.commit()
        except DotNetPersistenceError as exc:
            self._state = _State.FINISHED
            raise translate_dotnet_error(exc, entity="unit_of_work", operation="commit") from None
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
                except BaseException as caught:
                    if exc is None:
                        failure = caught
            transaction = self._transaction
            if transaction is not None and transaction.state is not DotNetTransactionState.FINISHED:
                try:
                    transaction.dispose()
                except DotNetPersistenceError as caught:
                    if exc is None and failure is None:
                        failure = translate_dotnet_error(
                            caught,
                            entity="unit_of_work",
                            operation="dispose_transaction",
                        )
        finally:
            connection = self._connection
            self._connection = None
            if connection is not None:
                close_failure = self._close_connection(connection)
                if exc is None and failure is None:
                    failure = close_failure
            self._state = _State.FINISHED
        if failure is not None:
            raise failure

    def _repository(self, repository: _Repository | None) -> _Repository:
        self._ensure_repository_operation()
        if repository is None:
            raise TransactionStateError("repository_access")
        return repository

    def _ensure_active(self, operation: str) -> None:
        if self._state is not _State.ACTIVE:
            raise TransactionStateError(operation)

    def _ensure_repository_operation(self) -> None:
        self._ensure_active("repository_operation")
        if self._rollback_only:
            raise TransactionStateError("repository_operation", "transaction_failed")

    def _mark_failed(self) -> None:
        self._rollback_only = True

    def _require_transaction(self, operation: str) -> DotNetTransaction:
        if self._transaction is None:
            raise TransactionStateError(operation)
        return self._transaction

    def _rollback_transaction(self) -> None:
        transaction = self._require_transaction("rollback")
        try:
            transaction.rollback()
        except DotNetPersistenceError as exc:
            self._state = _State.FINISHED
            raise translate_dotnet_error(exc, entity="unit_of_work", operation="rollback") from None
        self._state = _State.ROLLED_BACK

    @staticmethod
    def _close_connection(connection: object) -> BaseException | None:
        dynamic: Any = connection
        first_error: BaseException | None = None
        try:
            dynamic.Close()
        except Exception as exc:
            first_error = translate_dotnet_error(
                safe_persistence_error(exc, operation="close"),
                entity="unit_of_work",
                operation="close",
            )
        try:
            dynamic.Dispose()
        except Exception as exc:
            if first_error is None:
                first_error = translate_dotnet_error(
                    safe_persistence_error(exc, operation="dispose_connection"),
                    entity="unit_of_work",
                    operation="dispose_connection",
                )
        return first_error


@dataclass(frozen=True, slots=True)
class DotNetUnitOfWorkFactory:
    connection_factory: DotNetConnectionFactory = field(repr=False)

    def __call__(self) -> DotNetUnitOfWork:
        return DotNetUnitOfWork(self.connection_factory)


__all__ = ["DotNetUnitOfWork", "DotNetUnitOfWorkFactory"]
