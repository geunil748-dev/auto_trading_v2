"""Immutable Point-in-Time FeatureSnapshot domain model and digests."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots.errors import (
    FeatureSnapshotValidationError,
)
from auto_trading_v2.domain.feature_snapshots.serialization import (
    canonical_json,
    canonicalize_feature_values,
)
from auto_trading_v2.domain.primitives import FeatureSnapshotID, Symbol
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc

_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_RECORD_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_REASON_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SNAPSHOT_KEY_PATTERN = re.compile(r"^feature-snapshot:v1:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class TradingDayHorizon:
    """A bounded horizon whose unit is intentionally not calendar time."""

    value: int
    unit: ClassVar[str] = "TRADING_DAY"

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise FeatureSnapshotValidationError("거래일 horizon은 정수여야 합니다.")
        if not 1 <= self.value <= 5:
            raise FeatureSnapshotValidationError("거래일 horizon은 1~5여야 합니다.")


class FeatureQualityStatus(StrEnum):
    """Persistable snapshot quality states; BLOCKED is intentionally absent."""

    READY = "READY"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class FeatureProvenanceEntry:
    """Safe source identity and Point-in-Time availability evidence."""

    source_code: str
    source_record_key: str
    observed_at: datetime
    available_at: datetime
    content_digest: str
    source_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_code", _normalize_code(self.source_code, "source_code"))
        object.__setattr__(
            self,
            "source_record_key",
            _normalize_record_key(self.source_record_key),
        )
        if self.source_version is not None:
            object.__setattr__(
                self,
                "source_version",
                _normalize_code(self.source_version, "source_version"),
            )
        object.__setattr__(
            self,
            "observed_at",
            _normalize_timestamp(self.observed_at, "observed_at"),
        )
        object.__setattr__(
            self,
            "available_at",
            _normalize_timestamp(self.available_at, "available_at"),
        )
        if self.observed_at > self.available_at:
            raise FeatureSnapshotValidationError(
                "provenance observed_at은 available_at 이후일 수 없습니다."
            )
        if not isinstance(self.content_digest, str) or not _DIGEST_PATTERN.fullmatch(
            self.content_digest
        ):
            raise FeatureSnapshotValidationError(
                "provenance content_digest는 소문자 SHA-256이어야 합니다."
            )

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.source_code, self.source_record_key, self.source_version or "")

    @property
    def canonical_order(self) -> tuple[str, ...]:
        return (
            *self.identity,
            UtcTimestamp(self.observed_at).serialize(),
            UtcTimestamp(self.available_at).serialize(),
            self.content_digest,
        )

    def as_json(self) -> Mapping[str, object]:
        return {
            "available_at": UtcTimestamp(self.available_at).serialize(),
            "content_digest": self.content_digest,
            "observed_at": UtcTimestamp(self.observed_at).serialize(),
            "source_code": self.source_code,
            "source_record_key": self.source_record_key,
            "source_version": self.source_version,
        }


@dataclass(frozen=True, slots=True)
class FeatureSnapshotInput:
    """Validated immutable content used to derive identity and content hashes."""

    symbol: Symbol
    feature_set_code: str
    feature_set_version: str
    horizon: TradingDayHorizon
    as_of: datetime
    feature_values: Mapping[str, object] = field(repr=False)
    provenance: Sequence[FeatureProvenanceEntry] = field(repr=False)
    quality_status: FeatureQualityStatus
    quality_reason_codes: Sequence[str] = ()
    latest_input_available_at: datetime = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise FeatureSnapshotValidationError("symbol 타입이 올바르지 않습니다.")
        if not isinstance(self.horizon, TradingDayHorizon):
            raise FeatureSnapshotValidationError("horizon 타입이 올바르지 않습니다.")
        if not isinstance(self.quality_status, FeatureQualityStatus):
            raise FeatureSnapshotValidationError("quality_status 타입이 올바르지 않습니다.")
        object.__setattr__(
            self,
            "feature_set_code",
            _normalize_code(self.feature_set_code, "feature_set_code"),
        )
        object.__setattr__(
            self,
            "feature_set_version",
            _normalize_code(self.feature_set_version, "feature_set_version"),
        )
        object.__setattr__(self, "as_of", _normalize_timestamp(self.as_of, "as_of"))
        object.__setattr__(
            self,
            "feature_values",
            canonicalize_feature_values(self.feature_values),
        )
        provenance = _canonical_provenance(self.provenance, self.as_of)
        object.__setattr__(self, "provenance", provenance)
        reasons = _canonical_reason_codes(self.quality_reason_codes)
        if self.quality_status is FeatureQualityStatus.READY and reasons:
            raise FeatureSnapshotValidationError("READY snapshot에는 품질 사유가 없어야 합니다.")
        if self.quality_status is FeatureQualityStatus.DEGRADED and not reasons:
            raise FeatureSnapshotValidationError(
                "DEGRADED snapshot에는 하나 이상의 품질 사유가 필요합니다."
            )
        object.__setattr__(self, "quality_reason_codes", reasons)
        object.__setattr__(
            self,
            "latest_input_available_at",
            max(entry.available_at for entry in provenance),
        )


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """Canonical immutable stored FeatureSnapshot record."""

    feature_snapshot_id: FeatureSnapshotID
    snapshot_key: str
    content_digest: str
    snapshot_input: FeatureSnapshotInput = field(repr=False)
    generated_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.feature_snapshot_id, FeatureSnapshotID):
            raise FeatureSnapshotValidationError("feature_snapshot_id 타입이 올바르지 않습니다.")
        if not isinstance(self.snapshot_input, FeatureSnapshotInput):
            raise FeatureSnapshotValidationError("snapshot_input 타입이 올바르지 않습니다.")
        generated_at = _normalize_timestamp(self.generated_at, "generated_at")
        recorded_at = _normalize_timestamp(self.recorded_at, "recorded_at")
        if generated_at < self.snapshot_input.as_of:
            raise FeatureSnapshotValidationError("generated_at은 as_of 이전일 수 없습니다.")
        if not _SNAPSHOT_KEY_PATTERN.fullmatch(self.snapshot_key):
            raise FeatureSnapshotValidationError("snapshot_key 형식이 올바르지 않습니다.")
        if not _DIGEST_PATTERN.fullmatch(self.content_digest):
            raise FeatureSnapshotValidationError("content_digest 형식이 올바르지 않습니다.")
        if self.snapshot_key != feature_snapshot_key(self.snapshot_input):
            raise FeatureSnapshotValidationError("snapshot_key가 semantic identity와 다릅니다.")
        if self.content_digest != feature_content_digest(self.snapshot_input):
            raise FeatureSnapshotValidationError("content_digest가 snapshot 내용과 다릅니다.")
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "recorded_at", recorded_at)


def feature_snapshot_key(snapshot_input: FeatureSnapshotInput) -> str:
    identity = {
        "as_of": UtcTimestamp(snapshot_input.as_of).serialize(),
        "feature_set_code": snapshot_input.feature_set_code,
        "feature_set_version": snapshot_input.feature_set_version,
        "horizon_trading_days": snapshot_input.horizon.value,
        "symbol": snapshot_input.symbol.serialize(),
    }
    return f"feature-snapshot:v1:{_sha256(canonical_json(identity))}"


def feature_content_digest(snapshot_input: FeatureSnapshotInput) -> str:
    content = {
        "feature_values": snapshot_input.feature_values,
        "latest_input_available_at": UtcTimestamp(
            snapshot_input.latest_input_available_at
        ).serialize(),
        "provenance": [entry.as_json() for entry in snapshot_input.provenance],
        "quality_reason_codes": list(snapshot_input.quality_reason_codes),
        "quality_status": snapshot_input.quality_status.value,
    }
    return _sha256(canonical_json(content))


def _canonical_provenance(
    entries: Sequence[FeatureProvenanceEntry],
    as_of: datetime,
) -> tuple[FeatureProvenanceEntry, ...]:
    if isinstance(entries, str | bytes) or not isinstance(entries, Sequence) or not entries:
        raise FeatureSnapshotValidationError("provenance는 비어 있지 않아야 합니다.")
    if any(not isinstance(entry, FeatureProvenanceEntry) for entry in entries):
        raise FeatureSnapshotValidationError("provenance entry 타입이 올바르지 않습니다.")
    identities = [entry.identity for entry in entries]
    if len(identities) != len(set(identities)):
        raise FeatureSnapshotValidationError("중복 provenance entry는 허용되지 않습니다.")
    if any(entry.available_at > as_of for entry in entries):
        raise FeatureSnapshotValidationError("as_of 이후 이용 가능해진 입력은 저장할 수 없습니다.")
    return tuple(sorted(entries, key=lambda entry: entry.canonical_order))


def _canonical_reason_codes(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str | bytes) or not isinstance(values, Sequence):
        raise FeatureSnapshotValidationError("quality_reason_codes는 문자열 시퀀스여야 합니다.")
    if any(not isinstance(value, str) or not _REASON_PATTERN.fullmatch(value) for value in values):
        raise FeatureSnapshotValidationError("품질 사유 코드는 대문자 기술 코드여야 합니다.")
    if len(values) != len(set(values)):
        raise FeatureSnapshotValidationError("중복 품질 사유 코드는 허용되지 않습니다.")
    return tuple(sorted(values))


def _normalize_code(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise FeatureSnapshotValidationError(f"{label} 타입이 올바르지 않습니다.")
    normalized = value.strip()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise FeatureSnapshotValidationError(f"{label} 형식이 올바르지 않습니다.")
    return normalized


def _normalize_record_key(value: str) -> str:
    if not isinstance(value, str):
        raise FeatureSnapshotValidationError("source_record_key 타입이 올바르지 않습니다.")
    normalized = value.strip()
    if not _RECORD_KEY_PATTERN.fullmatch(normalized):
        raise FeatureSnapshotValidationError(
            "source_record_key는 안전한 불투명 기술 키여야 합니다."
        )
    return normalized


def _normalize_timestamp(value: datetime, label: str) -> datetime:
    try:
        return normalize_utc(value)
    except ValidationError:
        raise FeatureSnapshotValidationError(
            f"{label}은 timezone-aware datetime이어야 합니다."
        ) from None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
