"""Immutable creation and persistence contracts for FeatureSnapshot."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots import (
    FeatureProvenanceEntry,
    FeatureQualityStatus,
    FeatureSnapshot,
    FeatureSnapshotInput,
    FeatureSnapshotValidationError,
    TradingDayHorizon,
    feature_content_digest,
    feature_snapshot_key,
)
from auto_trading_v2.domain.primitives import FeatureSnapshotID, Symbol
from auto_trading_v2.domain.primitives.time import normalize_utc


@dataclass(frozen=True, slots=True)
class CreateFeatureSnapshotCommand:
    """Caller input validated and frozen before orchestration starts."""

    symbol: Symbol
    feature_set_code: str
    feature_set_version: str
    horizon: TradingDayHorizon
    as_of: datetime
    feature_values: Mapping[str, object] = field(repr=False)
    provenance: Sequence[FeatureProvenanceEntry] = field(repr=False)
    quality_status: FeatureQualityStatus
    quality_reason_codes: Sequence[str] = ()
    _snapshot_input: FeatureSnapshotInput = field(init=False, repr=False)

    def __post_init__(self) -> None:
        snapshot_input = FeatureSnapshotInput(
            symbol=self.symbol,
            feature_set_code=self.feature_set_code,
            feature_set_version=self.feature_set_version,
            horizon=self.horizon,
            as_of=self.as_of,
            feature_values=self.feature_values,
            provenance=self.provenance,
            quality_status=self.quality_status,
            quality_reason_codes=self.quality_reason_codes,
        )
        object.__setattr__(self, "_snapshot_input", snapshot_input)
        object.__setattr__(self, "symbol", snapshot_input.symbol)
        object.__setattr__(self, "feature_set_code", snapshot_input.feature_set_code)
        object.__setattr__(self, "feature_set_version", snapshot_input.feature_set_version)
        object.__setattr__(self, "horizon", snapshot_input.horizon)
        object.__setattr__(self, "as_of", snapshot_input.as_of)
        object.__setattr__(self, "feature_values", snapshot_input.feature_values)
        object.__setattr__(self, "provenance", snapshot_input.provenance)
        object.__setattr__(self, "quality_reason_codes", snapshot_input.quality_reason_codes)

    @property
    def snapshot_input(self) -> FeatureSnapshotInput:
        return self._snapshot_input


@dataclass(frozen=True, slots=True)
class NewFeatureSnapshot:
    """Insert-only contract; recorded_at remains database-owned."""

    feature_snapshot_id: FeatureSnapshotID
    snapshot_key: str
    content_digest: str
    snapshot_input: FeatureSnapshotInput = field(repr=False)
    generated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.feature_snapshot_id, FeatureSnapshotID):
            raise FeatureSnapshotValidationError("feature_snapshot_id 타입이 올바르지 않습니다.")
        if not isinstance(self.snapshot_input, FeatureSnapshotInput):
            raise FeatureSnapshotValidationError("snapshot_input 타입이 올바르지 않습니다.")
        try:
            generated_at = normalize_utc(self.generated_at)
        except ValidationError:
            raise FeatureSnapshotValidationError(
                "generated_at은 timezone-aware datetime이어야 합니다."
            ) from None
        if generated_at < self.snapshot_input.as_of:
            raise FeatureSnapshotValidationError("generated_at은 as_of 이전일 수 없습니다.")
        if self.snapshot_key != feature_snapshot_key(self.snapshot_input):
            raise FeatureSnapshotValidationError("snapshot_key가 semantic identity와 다릅니다.")
        if self.content_digest != feature_content_digest(self.snapshot_input):
            raise FeatureSnapshotValidationError("content_digest가 snapshot 내용과 다릅니다.")
        object.__setattr__(self, "generated_at", generated_at)

    def stored(self, recorded_at: datetime) -> FeatureSnapshot:
        return FeatureSnapshot(
            feature_snapshot_id=self.feature_snapshot_id,
            snapshot_key=self.snapshot_key,
            content_digest=self.content_digest,
            snapshot_input=self.snapshot_input,
            generated_at=self.generated_at,
            recorded_at=recorded_at,
        )


class FeatureSnapshotCreationOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class FeatureSnapshotCreationResult:
    outcome: FeatureSnapshotCreationOutcome
    snapshot: FeatureSnapshot
