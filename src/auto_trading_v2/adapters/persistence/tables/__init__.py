"""Canonical table registry in dependency creation order."""

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.tables.calibration_dataset_items import (
    probability_calibration_dataset_items,
)
from auto_trading_v2.adapters.persistence.tables.calibration_datasets import (
    probability_calibration_datasets,
)
from auto_trading_v2.adapters.persistence.tables.daily_market_bars import daily_market_bars
from auto_trading_v2.adapters.persistence.tables.events import trading_events
from auto_trading_v2.adapters.persistence.tables.execution import paper_fills, paper_orders
from auto_trading_v2.adapters.persistence.tables.feature_outcome_observations import (
    daily_feature_outcome_observation_run_items,
    daily_feature_outcome_observation_runs,
)
from auto_trading_v2.adapters.persistence.tables.feature_outcomes import (
    daily_feature_outcomes,
)
from auto_trading_v2.adapters.persistence.tables.feature_pipeline import (
    daily_feature_pipeline_items,
    daily_feature_pipeline_runs,
)
from auto_trading_v2.adapters.persistence.tables.feature_scoring import (
    daily_feature_scoring_items,
    daily_feature_scoring_runs,
)
from auto_trading_v2.adapters.persistence.tables.features import feature_snapshots
from auto_trading_v2.adapters.persistence.tables.market import (
    candidates,
    filter_evaluations,
    market_snapshots,
)
from auto_trading_v2.adapters.persistence.tables.outcome_labels import daily_feature_outcome_labels
from auto_trading_v2.adapters.persistence.tables.portfolio import (
    equity_snapshots,
    paper_positions,
    position_events,
)
from auto_trading_v2.adapters.persistence.tables.recommendations import recommendations
from auto_trading_v2.adapters.persistence.tables.strategy import (
    strategy_decisions,
    trade_intents,
)
from auto_trading_v2.adapters.persistence.tables.universes import universe_snapshots

BUSINESS_TABLES = (
    market_snapshots,
    daily_market_bars,
    feature_snapshots,
    recommendations,
    candidates,
    filter_evaluations,
    paper_positions,
    strategy_decisions,
    trade_intents,
    paper_orders,
    paper_fills,
    position_events,
    equity_snapshots,
    trading_events,
    universe_snapshots,
    daily_feature_pipeline_runs,
    daily_feature_pipeline_items,
    daily_feature_scoring_runs,
    daily_feature_scoring_items,
    daily_feature_outcomes,
    daily_feature_outcome_observation_runs,
    daily_feature_outcome_observation_run_items,
    daily_feature_outcome_labels,
    probability_calibration_datasets,
    probability_calibration_dataset_items,
)

__all__ = [
    "BUSINESS_TABLES",
    "candidates",
    "daily_market_bars",
    "daily_feature_pipeline_items",
    "daily_feature_pipeline_runs",
    "daily_feature_scoring_items",
    "daily_feature_scoring_runs",
    "daily_feature_outcome_observation_run_items",
    "daily_feature_outcome_labels",
    "daily_feature_outcome_observation_runs",
    "daily_feature_outcomes",
    "equity_snapshots",
    "filter_evaluations",
    "feature_snapshots",
    "market_snapshots",
    "metadata",
    "paper_fills",
    "paper_orders",
    "paper_positions",
    "probability_calibration_dataset_items",
    "probability_calibration_datasets",
    "position_events",
    "recommendations",
    "strategy_decisions",
    "trade_intents",
    "trading_events",
    "universe_snapshots",
]
