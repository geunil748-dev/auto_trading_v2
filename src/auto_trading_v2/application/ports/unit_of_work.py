"""Explicit transaction boundary independent of SQLAlchemy."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from auto_trading_v2.application.ports.paper_orders import PaperOrderRepository
from auto_trading_v2.application.ports.repositories import (
    CandidateRepository,
    FilterEvaluationRepository,
    MarketSnapshotRepository,
)
from auto_trading_v2.application.ports.strategy_decisions import StrategyDecisionRepository
from auto_trading_v2.application.ports.trade_intents import TradeIntentRepository


class UnitOfWork(Protocol):
    market_snapshots: MarketSnapshotRepository
    candidates: CandidateRepository
    filter_evaluations: FilterEvaluationRepository
    strategy_decisions: StrategyDecisionRepository
    trade_intents: TradeIntentRepository
    paper_orders: PaperOrderRepository

    def __enter__(self) -> Self: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
