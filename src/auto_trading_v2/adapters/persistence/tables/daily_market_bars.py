"""Canonical immutable completed daily market bar table."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    Index,
    Table,
    UniqueConstraint,
)

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    currency_type,
    decimal_type,
    non_empty_check_sql,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

daily_market_bars = Table(
    "daily_market_bars",
    metadata,
    Column("daily_market_bar_id", uuid_type(), primary_key=True),
    Column("bar_key", code_type(84), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("source_code", code_type(64), nullable=False),
    Column("source_record_key", code_type(160), nullable=False),
    Column("source_version", code_type(64), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("currency", currency_type(), nullable=False),
    Column("adjustment_basis", code_type(16), nullable=False),
    Column("session_date", Date(), nullable=False),
    Column("observed_at", timestamp_type(), nullable=False),
    Column("available_at", timestamp_type(), nullable=False),
    Column("open_price", decimal_type(), nullable=False),
    Column("high_price", decimal_type(), nullable=False),
    Column("low_price", decimal_type(), nullable=False),
    Column("close_price", decimal_type(), nullable=False),
    Column("volume", BigInteger(), nullable=True),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint(non_empty_check_sql("source_code"), name="source_code_nonempty"),
    CheckConstraint(
        non_empty_check_sql("source_record_key"),
        name="source_record_key_nonempty",
    ),
    CheckConstraint(
        non_empty_check_sql("source_version"),
        name="source_version_nonempty",
    ),
    CheckConstraint("currency = 'USD'", name="currency_usd"),
    CheckConstraint(
        "adjustment_basis IN ('RAW', 'SPLIT_ADJUSTED')",
        name="adjustment_basis",
    ),
    CheckConstraint("observed_at <= available_at", name="observed_before_available"),
    CheckConstraint(
        "open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0",
        name="prices_positive",
    ),
    CheckConstraint(
        "high_price >= low_price AND high_price >= open_price "
        "AND high_price >= close_price AND low_price <= open_price "
        "AND low_price <= close_price",
        name="ohlc_consistent",
    ),
    CheckConstraint("volume IS NULL OR volume >= 0", name="volume_nonnegative"),
    CheckConstraint(
        "DATALENGTH(bar_key) = 84 AND bar_key LIKE 'daily-market-bar:v1:%' "
        "AND RIGHT(bar_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="bar_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 "
        "AND content_digest COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("bar_key", name="uq_daily_market_bars_bar_key"),
    UniqueConstraint(
        "source_code",
        "source_record_key",
        "source_version",
        name="uq_daily_market_bars_semantic_identity",
    ),
    UniqueConstraint(
        "source_code",
        "symbol",
        "adjustment_basis",
        "session_date",
        "available_at",
        name="uq_daily_market_bars_session_revision",
    ),
    schema=SCHEMA,
)
Index(
    "ix_daily_market_bars_source_symbol_basis_session",
    daily_market_bars.c.source_code,
    daily_market_bars.c.symbol,
    daily_market_bars.c.adjustment_basis,
    daily_market_bars.c.session_date,
)
Index(
    "ix_daily_market_bars_source_symbol_available",
    daily_market_bars.c.source_code,
    daily_market_bars.c.symbol,
    daily_market_bars.c.available_at,
)
Index(
    "ix_daily_market_bars_symbol_session",
    daily_market_bars.c.symbol,
    daily_market_bars.c.session_date,
)
Index("ix_daily_market_bars_available", daily_market_bars.c.available_at)
