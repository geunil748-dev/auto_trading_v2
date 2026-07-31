"""Deterministic caller-provided universe identity and immutable snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.market_calendar import normalize_supported_mic
from auto_trading_v2.domain.primitives import Symbol, UniverseSnapshotID
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.universes.errors import UniverseSnapshotValidationError

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^universe:v1:[0-9a-f]{64}$")
MIN_MEMBERS = 1
MAX_MEMBERS = 100


@dataclass(frozen=True, slots=True)
class UniverseCode:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalized_code(self.value, "UNIVERSE_CODE_INVALID"))

    def serialize(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class UniverseVersion:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalized_code(self.value, "UNIVERSE_VERSION_INVALID"))

    def serialize(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class UniverseMember:
    symbol: Symbol
    mic_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise UniverseSnapshotValidationError("UNIVERSE_SYMBOL_INVALID")
        try:
            mic_code = normalize_supported_mic(self.mic_code)
        except Exception:
            raise UniverseSnapshotValidationError("UNIVERSE_MIC_UNSUPPORTED") from None
        object.__setattr__(self, "mic_code", mic_code)

    @property
    def canonical_order(self) -> tuple[str, str]:
        return (self.mic_code, self.symbol.serialize())

    def as_json(self) -> dict[str, str]:
        return {"mic_code": self.mic_code, "symbol": self.symbol.serialize()}


@dataclass(frozen=True, slots=True)
class UniverseDefinition:
    universe_code: UniverseCode
    universe_version: UniverseVersion
    members: Sequence[UniverseMember] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.universe_code, UniverseCode):
            raise UniverseSnapshotValidationError("UNIVERSE_CODE_INVALID")
        if not isinstance(self.universe_version, UniverseVersion):
            raise UniverseSnapshotValidationError("UNIVERSE_VERSION_INVALID")
        if isinstance(self.members, str | bytes) or not isinstance(self.members, Sequence):
            raise UniverseSnapshotValidationError("UNIVERSE_MEMBERS_INVALID")
        if not MIN_MEMBERS <= len(self.members) <= MAX_MEMBERS:
            raise UniverseSnapshotValidationError("UNIVERSE_MEMBER_COUNT_INVALID")
        if any(not isinstance(member, UniverseMember) for member in self.members):
            raise UniverseSnapshotValidationError("UNIVERSE_MEMBER_INVALID")
        symbols = [member.symbol for member in self.members]
        if len(symbols) != len(set(symbols)):
            raise UniverseSnapshotValidationError("UNIVERSE_DUPLICATE_SYMBOL")
        canonical = tuple(sorted(self.members, key=lambda member: member.canonical_order))
        object.__setattr__(self, "members", canonical)


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    universe_snapshot_id: UniverseSnapshotID
    universe_key: str
    content_digest: str
    definition: UniverseDefinition = field(repr=False)
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.universe_snapshot_id, UniverseSnapshotID):
            raise UniverseSnapshotValidationError("UNIVERSE_ID_INVALID")
        if not isinstance(self.definition, UniverseDefinition):
            raise UniverseSnapshotValidationError("UNIVERSE_DEFINITION_INVALID")
        if not isinstance(self.universe_key, str) or not _KEY.fullmatch(self.universe_key):
            raise UniverseSnapshotValidationError("UNIVERSE_KEY_INVALID")
        if not isinstance(self.content_digest, str) or not _DIGEST.fullmatch(self.content_digest):
            raise UniverseSnapshotValidationError("UNIVERSE_DIGEST_INVALID")
        if self.universe_key != universe_key(self.definition):
            raise UniverseSnapshotValidationError("UNIVERSE_KEY_MISMATCH")
        if self.content_digest != universe_content_digest(self.definition):
            raise UniverseSnapshotValidationError("UNIVERSE_DIGEST_MISMATCH")
        generated = _timestamp(self.generated_at, "UNIVERSE_GENERATED_AT_INVALID")
        recorded = _timestamp(self.recorded_at, "UNIVERSE_RECORDED_AT_INVALID")
        if generated > recorded:
            raise UniverseSnapshotValidationError("UNIVERSE_TIME_ORDER_INVALID")
        object.__setattr__(self, "generated_at", generated)
        object.__setattr__(self, "recorded_at", recorded)

    @property
    def universe_code(self) -> UniverseCode:
        return self.definition.universe_code

    @property
    def universe_version(self) -> UniverseVersion:
        return self.definition.universe_version

    @property
    def members(self) -> tuple[UniverseMember, ...]:
        return tuple(self.definition.members)


def universe_key(definition: UniverseDefinition) -> str:
    identity = {
        "universe_code": definition.universe_code.serialize(),
        "universe_version": definition.universe_version.serialize(),
    }
    return f"universe:v1:{_sha256(_canonical_json(identity))}"


def universe_content_digest(definition: UniverseDefinition) -> str:
    return _sha256(_canonical_json([member.as_json() for member in definition.members]))


def _normalized_code(value: object, category: str) -> str:
    if not isinstance(value, str):
        raise UniverseSnapshotValidationError(category)
    normalized = value.strip()
    if not _CODE.fullmatch(normalized):
        raise UniverseSnapshotValidationError(category)
    return normalized


def _timestamp(value: object, category: str) -> datetime:
    try:
        return normalize_utc(value)  # type: ignore[arg-type]
    except (TypeError, ValidationError):
        raise UniverseSnapshotValidationError(category) from None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
