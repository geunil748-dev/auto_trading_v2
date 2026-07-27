"""Safe JSON and row mapping for canonical FeatureSnapshot records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshot,
    FeatureSnapshotInput,
    FeatureSnapshotValidationError,
    TradingDayHorizon,
    canonical_json,
)
from auto_trading_v2.domain.primitives import FeatureSnapshotID, Symbol


def serialize_feature_values(snapshot_input: FeatureSnapshotInput) -> str:
    return canonical_json(snapshot_input.feature_values)


def serialize_provenance(snapshot_input: FeatureSnapshotInput) -> str:
    return canonical_json([entry.as_json() for entry in snapshot_input.provenance])


def serialize_quality_reasons(snapshot_input: FeatureSnapshotInput) -> str:
    return canonical_json(list(snapshot_input.quality_reason_codes))


def map_feature_snapshot(row: Mapping[Any, Any]) -> FeatureSnapshot:
    """Map a row without exposing rejected stored JSON in raised errors."""

    try:
        feature_values = _json_object(row["feature_values"])
        provenance = tuple(_provenance_entry(item) for item in _json_array(row["provenance"]))
        reasons = _json_array(row["quality_reason_codes"])
        reason_codes = tuple(_string(reason) for reason in reasons)
        snapshot_input = FeatureSnapshotInput(
            symbol=Symbol(str(row["symbol"])),
            feature_set_code=str(row["feature_set_code"]),
            feature_set_version=str(row["feature_set_version"]),
            horizon=TradingDayHorizon(int(row["horizon_trading_days"])),
            as_of=_datetime(row["as_of"]),
            feature_values=feature_values,
            provenance=provenance,
            quality_status=FeatureQualityStatus(str(row["quality_status"])),
            quality_reason_codes=reason_codes,
        )
        if snapshot_input.latest_input_available_at != _datetime(row["latest_input_available_at"]):
            raise ValueError
        return FeatureSnapshot(
            feature_snapshot_id=FeatureSnapshotID(_uuid(row["feature_snapshot_id"])),
            snapshot_key=str(row["snapshot_key"]),
            content_digest=str(row["content_digest"]),
            snapshot_input=snapshot_input,
            generated_at=_datetime(row["generated_at"]),
            recorded_at=_datetime(row["recorded_at"]),
        )
    except (
        FeatureSnapshotValidationError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        raise PersistenceMappingError("feature_snapshot") from None


def _provenance_entry(value: object) -> FeatureProvenanceEntry:
    if not isinstance(value, dict) or set(value) != {
        "available_at",
        "content_digest",
        "observed_at",
        "source_code",
        "source_record_key",
        "source_version",
    }:
        raise TypeError
    source_version = value["source_version"]
    if source_version is not None and not isinstance(source_version, str):
        raise TypeError
    return FeatureProvenanceEntry(
        source_code=_string(value["source_code"]),
        source_record_key=_string(value["source_record_key"]),
        observed_at=_parsed_datetime(value["observed_at"]),
        available_at=_parsed_datetime(value["available_at"]),
        content_digest=_string(value["content_digest"]),
        source_version=source_version,
    )


def _json_object(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        raise TypeError
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise TypeError
    return decoded


def _json_array(value: object) -> list[object]:
    if not isinstance(value, str):
        raise TypeError
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        raise TypeError
    return decoded


def _parsed_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value
