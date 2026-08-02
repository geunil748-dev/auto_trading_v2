"""Explicit transaction boundary independent of SQLAlchemy."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from auto_trading_v2.application.ports.daily_market_bars import DailyMarketBarRepository
from auto_trading_v2.application.ports.feature_pipeline import (
    DailyFeaturePipelineRunRepository,
)
from auto_trading_v2.application.ports.feature_scoring import (
    DailyFeatureScoringRunRepository,
)
from auto_trading_v2.application.ports.feature_snapshots import FeatureSnapshotRepository
from auto_trading_v2.application.ports.paper_fills import PaperFillRepository
from auto_trading_v2.application.ports.paper_orders import PaperOrderRepository
from auto_trading_v2.application.ports.position_projection import (
    PaperPositionRepository,
    PositionEventRepository,
)
from auto_trading_v2.application.ports.recommendations import RecommendationRepository
from auto_trading_v2.application.ports.repositories import (
    CandidateRepository,
    FilterEvaluationRepository,
    MarketSnapshotRepository,
)
from auto_trading_v2.application.ports.strategy_decisions import StrategyDecisionRepository
from auto_trading_v2.application.ports.trade_intents import TradeIntentRepository
from auto_trading_v2.application.ports.universes import UniverseSnapshotRepository


class UnitOfWork(Protocol):
    daily_market_bars: DailyMarketBarRepository
    feature_snapshots: FeatureSnapshotRepository
    universe_snapshots: UniverseSnapshotRepository
    daily_feature_pipeline_runs: DailyFeaturePipelineRunRepository
    daily_feature_scoring_runs: DailyFeatureScoringRunRepository
    recommendations: RecommendationRepository
    market_snapshots: MarketSnapshotRepository
    candidates: CandidateRepository
    filter_evaluations: FilterEvaluationRepository
    strategy_decisions: StrategyDecisionRepository
    trade_intents: TradeIntentRepository
    paper_orders: PaperOrderRepository
    paper_fills: PaperFillRepository
    paper_positions: PaperPositionRepository
    position_events: PositionEventRepository

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
