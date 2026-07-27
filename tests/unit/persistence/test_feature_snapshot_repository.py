from datetime import UTC, datetime
from decimal import Decimal
from inspect import getmembers, isfunction
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy import Connection

from auto_trading_v2.adapters.persistence.feature_snapshot_mapping import (
    map_feature_snapshot,
    serialize_feature_values,
    serialize_provenance,
    serialize_quality_reasons,
)
from auto_trading_v2.adapters.persistence.repositories.feature_snapshots import (
    SqlAlchemyFeatureSnapshotRepository,
)
from auto_trading_v2.application.contracts.feature_snapshots import NewFeatureSnapshot
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.ports.feature_snapshots import FeatureSnapshotRepository
from auto_trading_v2.domain.feature_snapshots import (
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives import FeatureSnapshotID
from tests.unit.application.feature_snapshot_fakes import (
    GENERATED_AT,
    command,
)


def _new_snapshot() -> NewFeatureSnapshot:
    source = command({"close": Decimal("100.2500")}).snapshot_input
    return NewFeatureSnapshot(
        feature_snapshot_id=FeatureSnapshotID(UUID(int=1)),
        snapshot_key=feature_snapshot_key(source),
        content_digest=feature_content_digest(source),
        snapshot_input=source,
        generated_at=GENERATED_AT,
    )


def _row(snapshot: NewFeatureSnapshot | None = None) -> dict[str, object]:
    value = _new_snapshot() if snapshot is None else snapshot
    source = value.snapshot_input
    return {
        "feature_snapshot_id": value.feature_snapshot_id.value,
        "snapshot_key": value.snapshot_key,
        "content_digest": value.content_digest,
        "symbol": source.symbol.value,
        "feature_set_code": source.feature_set_code,
        "feature_set_version": source.feature_set_version,
        "horizon_trading_days": source.horizon.value,
        "as_of": source.as_of,
        "generated_at": value.generated_at,
        "latest_input_available_at": source.latest_input_available_at,
        "quality_status": source.quality_status.value,
        "quality_reason_codes": serialize_quality_reasons(source),
        "feature_values": serialize_feature_values(source),
        "provenance": serialize_provenance(source),
        "recorded_at": datetime(2026, 7, 20, 15, 0, 2, tzinfo=UTC),
    }


def test_repository_protocol_is_insert_only_with_two_precise_getters() -> None:
    methods = {
        name
        for name, value in getmembers(FeatureSnapshotRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {"add", "get_by_id", "get_by_snapshot_key"}
    assert not {"update", "delete", "upsert", "commit", "rollback"}.intersection(methods)


def test_canonical_json_and_mapping_round_trip_decimal_time_and_provenance() -> None:
    mapped = map_feature_snapshot(_row())

    assert mapped.snapshot_input.feature_values["close"] == "100.25"
    assert mapped.snapshot_input.as_of.tzinfo is UTC
    assert mapped.snapshot_input.latest_input_available_at.tzinfo is UTC
    assert mapped.snapshot_input.provenance[0].source_record_key == "row-1"
    assert serialize_feature_values(mapped.snapshot_input) == '{"close":"100.25"}'
    assert serialize_quality_reasons(mapped.snapshot_input) == "[]"


@pytest.mark.parametrize(
    ("column", "raw"),
    [
        ("feature_values", '{"secret":"value","number":1.5}'),
        ("provenance", '[{"secret":"value"}]'),
        ("quality_reason_codes", '["secret=value"]'),
    ],
)
def test_invalid_stored_json_is_rejected_without_raw_content(
    column: str,
    raw: str,
) -> None:
    row = _row()
    row[column] = raw

    with pytest.raises(PersistenceMappingError) as captured:
        map_feature_snapshot(row)

    assert raw not in str(captured.value)
    assert "secret" not in str(captured.value)


def test_sqlalchemy_repository_add_uses_caller_connection_without_commit() -> None:
    connection = MagicMock()
    selected = MagicMock()
    selected.mappings.return_value.one_or_none.return_value = _row()
    connection.execute.side_effect = [MagicMock(), selected]
    repository = SqlAlchemyFeatureSnapshotRepository(cast(Connection, connection))

    stored = repository.add(_new_snapshot())

    assert stored.feature_snapshot_id == FeatureSnapshotID(UUID(int=1))
    assert connection.execute.call_count == 2
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


@pytest.mark.parametrize("getter", ["get_by_id", "get_by_snapshot_key"])
def test_repository_getters_use_canonical_mapping(getter: str) -> None:
    connection = MagicMock()
    selected = MagicMock()
    selected.mappings.return_value.one_or_none.return_value = _row()
    connection.execute.return_value = selected
    repository = SqlAlchemyFeatureSnapshotRepository(cast(Connection, connection))

    if getter == "get_by_id":
        stored = repository.get_by_id(FeatureSnapshotID(UUID(int=1)))
    else:
        stored = repository.get_by_snapshot_key(_new_snapshot().snapshot_key)

    assert stored is not None
    assert stored.content_digest == _new_snapshot().content_digest


def test_repository_type_owns_no_transaction_or_mutating_rewrite_methods() -> None:
    names = set(dir(SqlAlchemyFeatureSnapshotRepository))

    assert not {"commit", "rollback", "begin", "update", "delete", "upsert"}.intersection(names)
