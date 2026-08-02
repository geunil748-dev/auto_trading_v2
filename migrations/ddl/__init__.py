"""Frozen DDL helpers for the initial canonical MSSQL revision."""

from migrations.ddl.daily_market_bars import create_daily_market_bars_table
from migrations.ddl.events import create_trading_events
from migrations.ddl.execution import create_execution_tables
from migrations.ddl.feature_outcomes import create_daily_feature_outcome_tables
from migrations.ddl.feature_pipeline import create_multi_symbol_feature_pipeline_tables
from migrations.ddl.feature_scoring import create_daily_feature_scoring_tables
from migrations.ddl.features import create_feature_snapshot_table
from migrations.ddl.market import create_market_tables
from migrations.ddl.portfolio import create_portfolio_tables
from migrations.ddl.recommendations import create_recommendations_table
from migrations.ddl.strategy import create_strategy_tables

__all__ = [
    "create_execution_tables",
    "create_daily_market_bars_table",
    "create_feature_snapshot_table",
    "create_daily_feature_scoring_tables",
    "create_daily_feature_outcome_tables",
    "create_market_tables",
    "create_multi_symbol_feature_pipeline_tables",
    "create_portfolio_tables",
    "create_recommendations_table",
    "create_strategy_tables",
    "create_trading_events",
]
