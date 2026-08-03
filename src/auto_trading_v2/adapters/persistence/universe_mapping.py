"""Safe JSON and row mapping for canonical UniverseSnapshot records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from auto_trading_v2.application.contracts.universes import NewUniverseSnapshot
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import Symbol, UniverseSnapshotID
from auto_trading_v2.domain.universes import (
    UniverseCode,
    UniverseDefinition,
    UniverseMember,
    UniverseSnapshot,
    UniverseVersion,
)


def serialize_universe_members(definition: UniverseDefinition) -> str:
    return json.dumps(
        [member.as_json() for member in definition.members],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def new_universe_snapshot_values(snapshot: NewUniverseSnapshot) -> dict[str, object]:
    definition = snapshot.definition
    return {
        "universe_snapshot_id": snapshot.universe_snapshot_id.value,
        "universe_key": snapshot.universe_key,
        "content_digest": snapshot.content_digest,
        "universe_code": definition.universe_code.value,
        "universe_version": definition.universe_version.value,
        "member_count": len(definition.members),
        "members": serialize_universe_members(definition),
        "generated_at": snapshot.generated_at,
    }


def map_universe_snapshot(row: Mapping[Any, Any]) -> UniverseSnapshot:
    try:
        decoded = json.loads(_string(row["members"]))
        if not isinstance(decoded, list):
            raise TypeError
        members = tuple(_member(value) for value in decoded)
        if len(members) != _integer(row["member_count"]):
            raise ValueError
        definition = UniverseDefinition(
            UniverseCode(_string(row["universe_code"])),
            UniverseVersion(_string(row["universe_version"])),
            members,
        )
        return UniverseSnapshot(
            UniverseSnapshotID(_uuid(row["universe_snapshot_id"])),
            _string(row["universe_key"]),
            _string(row["content_digest"]),
            definition,
            _datetime(row["generated_at"]),
            _datetime(row["recorded_at"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise PersistenceMappingError("universe_snapshot") from None


def _member(value: object) -> UniverseMember:
    if not isinstance(value, dict) or set(value) != {"mic_code", "symbol"}:
        raise TypeError
    return UniverseMember(Symbol(_string(value["symbol"])), _string(value["mic_code"]))


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError
    return value
