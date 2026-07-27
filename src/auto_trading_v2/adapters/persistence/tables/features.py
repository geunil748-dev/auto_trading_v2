"""Canonical Point-in-Time feature snapshot table."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    SmallInteger,
    Table,
    UniqueConstraint,
)

from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.types import (
    code_type,
    json_array_check_sql,
    json_object_check_sql,
    json_text_type,
    non_empty_check_sql,
    symbol_check_sql,
    symbol_type,
    timestamp_type,
    utc_server_default,
    uuid_type,
)

SCHEMA = "trading"

feature_snapshots = Table(
    "feature_snapshots",
    metadata,
    Column("feature_snapshot_id", uuid_type(), primary_key=True),
    Column("snapshot_key", code_type(84), nullable=False),
    Column("content_digest", code_type(64), nullable=False),
    Column("symbol", symbol_type(), nullable=False),
    Column("feature_set_code", code_type(64), nullable=False),
    Column("feature_set_version", code_type(64), nullable=False),
    Column("horizon_trading_days", SmallInteger(), nullable=False),
    Column("as_of", timestamp_type(), nullable=False),
    Column("generated_at", timestamp_type(), nullable=False),
    Column("latest_input_available_at", timestamp_type(), nullable=False),
    Column("quality_status", code_type(16), nullable=False),
    Column("quality_reason_codes", json_text_type(), nullable=False),
    Column("feature_values", json_text_type(), nullable=False),
    Column("provenance", json_text_type(), nullable=False),
    Column(
        "recorded_at",
        timestamp_type(),
        nullable=False,
        server_default=utc_server_default(),
    ),
    CheckConstraint(symbol_check_sql(), name="symbol"),
    CheckConstraint(non_empty_check_sql("feature_set_code"), name="feature_set_code_nonempty"),
    CheckConstraint(
        non_empty_check_sql("feature_set_version"),
        name="feature_set_version_nonempty",
    ),
    CheckConstraint("horizon_trading_days BETWEEN 1 AND 5", name="horizon"),
    CheckConstraint("generated_at >= as_of", name="generated_after_cutoff"),
    CheckConstraint(
        "latest_input_available_at <= as_of",
        name="latest_input_before_cutoff",
    ),
    CheckConstraint("quality_status IN ('READY', 'DEGRADED')", name="quality_status"),
    CheckConstraint(
        json_array_check_sql("quality_reason_codes"),
        name="quality_reason_codes_json_array",
    ),
    CheckConstraint(json_object_check_sql("feature_values"), name="feature_values_json_object"),
    CheckConstraint(json_array_check_sql("provenance"), name="provenance_json_array"),
    CheckConstraint("feature_values <> '{}'", name="feature_values_nonempty"),
    CheckConstraint("provenance <> '[]'", name="provenance_nonempty"),
    CheckConstraint(
        "(quality_status = 'READY' AND quality_reason_codes = '[]') "
        "OR (quality_status = 'DEGRADED' AND quality_reason_codes <> '[]')",
        name="quality_reasons",
    ),
    CheckConstraint(
        "DATALENGTH(snapshot_key) = 84 AND snapshot_key LIKE 'feature-snapshot:v1:%'",
        name="snapshot_key_format",
    ),
    CheckConstraint(
        "DATALENGTH(content_digest) = 64 "
        "AND content_digest COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
        name="content_digest_format",
    ),
    UniqueConstraint("snapshot_key", name="uq_feature_snapshots_snapshot_key"),
    UniqueConstraint(
        "symbol",
        "feature_set_code",
        "feature_set_version",
        "horizon_trading_days",
        "as_of",
        name="uq_feature_snapshots_semantic_identity",
    ),
    schema=SCHEMA,
)
Index(
    "ix_feature_snapshots_symbol_as_of",
    feature_snapshots.c.symbol,
    feature_snapshots.c.as_of,
)
Index(
    "ix_feature_snapshots_set_as_of",
    feature_snapshots.c.feature_set_code,
    feature_snapshots.c.feature_set_version,
    feature_snapshots.c.as_of,
)
Index(
    "ix_feature_snapshots_quality_as_of",
    feature_snapshots.c.quality_status,
    feature_snapshots.c.as_of,
)
Index("ix_feature_snapshots_content_digest", feature_snapshots.c.content_digest)
