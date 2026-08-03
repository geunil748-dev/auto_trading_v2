"""Canonical immutable caller-provided universe snapshots."""

from sqlalchemy import CheckConstraint, Column, Index, SmallInteger, Table, UniqueConstraint

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    json_array_check_sql,
    json_text_type,
    non_empty_check_sql,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

universe_snapshots = Table(
    "universe_snapshots",
    metadata,
    Column("universe_snapshot_id", uuid_type(), primary_key=True),
    Column("universe_key", code_type(76), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("universe_code", code_type(64), nullable=False),
    Column("universe_version", code_type(64), nullable=False),
    Column("member_count", SmallInteger(), nullable=False),
    Column("members", json_text_type(), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("recorded_at", timestamp_type(), nullable=False, server_default=utc_server_default()),
    CheckConstraint(non_empty_check_sql("universe_code"), name="universe_code_nonempty"),
    CheckConstraint(
        non_empty_check_sql("universe_version"),
        name="universe_version_nonempty",
    ),
    CheckConstraint("member_count BETWEEN 1 AND 100", name="member_count"),
    CheckConstraint(json_array_check_sql("members"), name="members_json_array"),
    CheckConstraint("members <> '[]'", name="members_nonempty"),
    CheckConstraint("generated_at <= recorded_at", name="time_order"),
    CheckConstraint(
        "DATALENGTH(universe_key) = 76 AND universe_key LIKE 'universe:v1:%' "
        "AND RIGHT(universe_key, 64) COLLATE Latin1_General_100_BIN2 "
        "NOT LIKE '%[^0-9a-f]%'",
        name="universe_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 AND content_digest "
        "COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("universe_key", name="uq_universe_snapshots_universe_key"),
    UniqueConstraint(
        "universe_code",
        "universe_version",
        name="uq_universe_snapshots_code_version",
    ),
    schema=SCHEMA,
)
Index(
    "ix_universe_snapshots_code_version",
    universe_snapshots.c.universe_code,
    universe_snapshots.c.universe_version,
)
Index("ix_universe_snapshots_generated", universe_snapshots.c.generated_at)
