"""Additive DDL for canonical completed daily market bars."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    currency_type,
    decimal_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)


def _check(sql: str, name: str) -> sa.CheckConstraint:
    return named_check_constraint(sql, name=f"ck_daily_market_bars_{name}")


def create_daily_market_bars_table(op: Operations) -> None:
    """Create only trading.daily_market_bars."""

    op.create_table(
        "daily_market_bars",
        sa.Column("daily_market_bar_id", uuid_type(), nullable=False),
        sa.Column("bar_key", code_type(84), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("source_code", code_type(64), nullable=False),
        sa.Column("source_record_key", code_type(160), nullable=False),
        sa.Column("source_version", code_type(64), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("currency", currency_type(), nullable=False),
        sa.Column("adjustment_basis", code_type(16), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("observed_at", timestamp_type(), nullable=False),
        sa.Column("available_at", timestamp_type(), nullable=False),
        sa.Column("open_price", decimal_type(), nullable=False),
        sa.Column("high_price", decimal_type(), nullable=False),
        sa.Column("low_price", decimal_type(), nullable=False),
        sa.Column("close_price", decimal_type(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("daily_market_bar_id", name="pk_daily_market_bars"),
        _check(symbol_check(), "symbol"),
        _check("DATALENGTH(LTRIM(RTRIM(source_code))) > 0", "source_code_nonempty"),
        _check(
            "DATALENGTH(LTRIM(RTRIM(source_record_key))) > 0",
            "source_record_key_nonempty",
        ),
        _check(
            "DATALENGTH(LTRIM(RTRIM(source_version))) > 0",
            "source_version_nonempty",
        ),
        _check("currency = 'USD'", "currency_usd"),
        _check(
            "adjustment_basis IN ('RAW', 'SPLIT_ADJUSTED')",
            "adjustment_basis",
        ),
        _check("observed_at <= available_at", "observed_before_available"),
        _check(
            "open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0",
            "prices_positive",
        ),
        _check(
            "high_price >= low_price AND high_price >= open_price "
            "AND high_price >= close_price AND low_price <= open_price "
            "AND low_price <= close_price",
            "ohlc_consistent",
        ),
        _check("volume IS NULL OR volume >= 0", "volume_nonnegative"),
        _check(
            "DATALENGTH(bar_key) = 84 AND bar_key LIKE 'daily-market-bar:v1:%' "
            "AND RIGHT(bar_key, 64) COLLATE Latin1_General_100_BIN2 "
            "NOT LIKE '%[^0-9a-f]%'",
            "bar_key_format",
        ),
        _check(
            "DATALENGTH(content_digest) = 64 "
            "AND content_digest COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
            "content_digest_format",
        ),
        sa.UniqueConstraint("bar_key", name="uq_daily_market_bars_bar_key"),
        sa.UniqueConstraint(
            "source_code",
            "source_record_key",
            "source_version",
            name="uq_daily_market_bars_semantic_identity",
        ),
        sa.UniqueConstraint(
            "source_code",
            "symbol",
            "adjustment_basis",
            "session_date",
            "available_at",
            name="uq_daily_market_bars_session_revision",
        ),
        schema=SCHEMA,
    )
    indexes = (
        (
            "ix_daily_market_bars_source_symbol_basis_session",
            ["source_code", "symbol", "adjustment_basis", "session_date"],
        ),
        (
            "ix_daily_market_bars_source_symbol_available",
            ["source_code", "symbol", "available_at"],
        ),
        ("ix_daily_market_bars_symbol_session", ["symbol", "session_date"]),
        ("ix_daily_market_bars_available", ["available_at"]),
    )
    for name, columns in indexes:
        op.create_index(name, "daily_market_bars", columns, schema=SCHEMA)
