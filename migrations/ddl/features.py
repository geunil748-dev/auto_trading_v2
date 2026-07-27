"""Additive DDL for canonical Point-in-Time feature snapshots."""

import sqlalchemy as sa
from alembic.operations import Operations

from migrations.ddl.common import (
    SCHEMA,
    UTC_DEFAULT,
    code_type,
    json_array_check,
    json_object_check,
    json_type,
    named_check_constraint,
    symbol_check,
    symbol_type,
    timestamp_type,
    uuid_type,
)


def create_feature_snapshot_table(op: Operations) -> None:
    """Create only the independent trading.feature_snapshots table."""

    op.create_table(
        "feature_snapshots",
        sa.Column("feature_snapshot_id", uuid_type(), nullable=False),
        sa.Column("snapshot_key", code_type(84), nullable=False),
        sa.Column("content_digest", code_type(64), nullable=False),
        sa.Column("symbol", symbol_type(), nullable=False),
        sa.Column("feature_set_code", code_type(64), nullable=False),
        sa.Column("feature_set_version", code_type(64), nullable=False),
        sa.Column("horizon_trading_days", sa.SmallInteger(), nullable=False),
        sa.Column("as_of", timestamp_type(), nullable=False),
        sa.Column("generated_at", timestamp_type(), nullable=False),
        sa.Column("latest_input_available_at", timestamp_type(), nullable=False),
        sa.Column("quality_status", code_type(16), nullable=False),
        sa.Column("quality_reason_codes", json_type(), nullable=False),
        sa.Column("feature_values", json_type(), nullable=False),
        sa.Column("provenance", json_type(), nullable=False),
        sa.Column("recorded_at", timestamp_type(), server_default=UTC_DEFAULT, nullable=False),
        sa.PrimaryKeyConstraint("feature_snapshot_id", name="pk_feature_snapshots"),
        named_check_constraint(symbol_check(), name="ck_feature_snapshots_symbol"),
        named_check_constraint(
            "DATALENGTH(LTRIM(RTRIM(feature_set_code))) > 0",
            name="ck_feature_snapshots_feature_set_code_nonempty",
        ),
        named_check_constraint(
            "DATALENGTH(LTRIM(RTRIM(feature_set_version))) > 0",
            name="ck_feature_snapshots_feature_set_version_nonempty",
        ),
        named_check_constraint(
            "horizon_trading_days BETWEEN 1 AND 5",
            name="ck_feature_snapshots_horizon",
        ),
        named_check_constraint(
            "generated_at >= as_of",
            name="ck_feature_snapshots_generated_after_cutoff",
        ),
        named_check_constraint(
            "latest_input_available_at <= as_of",
            name="ck_feature_snapshots_latest_input_before_cutoff",
        ),
        named_check_constraint(
            "quality_status IN ('READY', 'DEGRADED')",
            name="ck_feature_snapshots_quality_status",
        ),
        named_check_constraint(
            json_array_check("quality_reason_codes"),
            name="ck_feature_snapshots_quality_reason_codes_json_array",
        ),
        named_check_constraint(
            json_object_check("feature_values"),
            name="ck_feature_snapshots_feature_values_json_object",
        ),
        named_check_constraint(
            json_array_check("provenance"),
            name="ck_feature_snapshots_provenance_json_array",
        ),
        named_check_constraint(
            "feature_values <> '{}'",
            name="ck_feature_snapshots_feature_values_nonempty",
        ),
        named_check_constraint(
            "provenance <> '[]'",
            name="ck_feature_snapshots_provenance_nonempty",
        ),
        named_check_constraint(
            "(quality_status = 'READY' AND quality_reason_codes = '[]') "
            "OR (quality_status = 'DEGRADED' AND quality_reason_codes <> '[]')",
            name="ck_feature_snapshots_quality_reasons",
        ),
        named_check_constraint(
            "DATALENGTH(snapshot_key) = 84 AND snapshot_key LIKE 'feature-snapshot:v1:%'",
            name="ck_feature_snapshots_snapshot_key_format",
        ),
        named_check_constraint(
            "DATALENGTH(content_digest) = 64 "
            "AND content_digest COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
            name="ck_feature_snapshots_content_digest_format",
        ),
        sa.UniqueConstraint(
            "snapshot_key",
            name="uq_feature_snapshots_snapshot_key",
        ),
        sa.UniqueConstraint(
            "symbol",
            "feature_set_code",
            "feature_set_version",
            "horizon_trading_days",
            "as_of",
            name="uq_feature_snapshots_semantic_identity",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_feature_snapshots_symbol_as_of",
        "feature_snapshots",
        ["symbol", "as_of"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_feature_snapshots_set_as_of",
        "feature_snapshots",
        ["feature_set_code", "feature_set_version", "as_of"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_feature_snapshots_quality_as_of",
        "feature_snapshots",
        ["quality_status", "as_of"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_feature_snapshots_content_digest",
        "feature_snapshots",
        ["content_digest"],
        schema=SCHEMA,
    )
