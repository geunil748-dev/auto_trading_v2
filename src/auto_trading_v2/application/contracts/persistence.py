"""Immutable contracts for the first canonical persistence slice."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import cast, overload

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    FilterEvaluationID,
    FilterSetID,
    MarketSnapshotID,
    Price,
    RunID,
    SessionDate,
    Symbol,
)
from auto_trading_v2.domain.primitives.time import normalize_utc

type JSONValue = None | bool | int | str | list[JSONValue] | Mapping[str, JSONValue]
type FrozenJSONValue = None | bool | int | str | FrozenJSONList | Mapping[str, FrozenJSONValue]


@dataclass(frozen=True, slots=True)
class FrozenJSONList(Sequence[FrozenJSONValue]):
    """Internal immutable representation of an accepted JSON list."""

    _items: tuple[FrozenJSONValue, ...] = field(repr=False)

    @overload
    def __getitem__(self, index: int) -> FrozenJSONValue: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[FrozenJSONValue]: ...

    def __getitem__(self, index: int | slice) -> FrozenJSONValue | Sequence[FrozenJSONValue]:
        return self._items[index]

    def __iter__(self) -> Iterator[FrozenJSONValue]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def freeze_json_object(value: Mapping[str, JSONValue]) -> Mapping[str, JSONValue]:
    """Validate a top-level JSON object and return a deeply immutable copy."""

    if not isinstance(value, Mapping):
        raise ValidationError("details must be a JSON object")
    frozen = _freeze_json_mapping(value)
    return cast(Mapping[str, JSONValue], frozen)


def _freeze_json_mapping(value: Mapping[str, object]) -> Mapping[str, FrozenJSONValue]:
    frozen: dict[str, FrozenJSONValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValidationError("JSON object keys must be strings")
        frozen[key] = _freeze_json_value(item)
    return MappingProxyType(frozen)


def _freeze_json_value(value: object) -> FrozenJSONValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, FrozenJSONList):
        return FrozenJSONList(tuple(_freeze_json_value(item) for item in value))
    if isinstance(value, list):
        return FrozenJSONList(tuple(_freeze_json_value(item) for item in value))
    if isinstance(value, Mapping):
        return _freeze_json_mapping(value)
    raise ValidationError("details contains an unsupported JSON value")


def _require_instance(value: object, expected: type[object], label: str) -> None:
    if not isinstance(value, expected):
        raise ValidationError(f"{label} has an invalid type")


def _normalize_code(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must not be empty")
    normalized = value.strip()
    if len(normalized) > 64:
        raise ValidationError(f"{label} is too long")
    return normalized


def _validate_optional_decimal(value: Decimal | None, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValidationError(f"{label} must be a finite Decimal")


@dataclass(frozen=True, slots=True)
class NewMarketSnapshot:
    market_snapshot_id: MarketSnapshotID
    symbol: Symbol
    session_date: SessionDate
    observed_at: datetime
    source: str
    open_price: Price
    high_price: Price
    low_price: Price
    last_price: Price
    previous_high_price: Price
    previous_low_price: Price
    previous_close_price: Price | None
    volume: int | None

    def __post_init__(self) -> None:
        _require_instance(self.market_snapshot_id, MarketSnapshotID, "market_snapshot_id")
        _require_instance(self.symbol, Symbol, "symbol")
        _require_instance(self.session_date, SessionDate, "session_date")
        for name in (
            "open_price",
            "high_price",
            "low_price",
            "last_price",
            "previous_high_price",
            "previous_low_price",
        ):
            _require_instance(getattr(self, name), Price, name)
        if self.previous_close_price is not None:
            _require_instance(self.previous_close_price, Price, "previous_close_price")
        if self.volume is not None and (
            isinstance(self.volume, bool) or not isinstance(self.volume, int) or self.volume < 0
        ):
            raise ValidationError("volume must be a non-negative integer or None")
        object.__setattr__(self, "source", _normalize_code(self.source, "source"))
        object.__setattr__(self, "observed_at", normalize_utc(self.observed_at))


@dataclass(frozen=True, slots=True)
class StoredMarketSnapshot(NewMarketSnapshot):
    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredMarketSnapshot, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))


@dataclass(frozen=True, slots=True)
class NewCandidate:
    candidate_id: CandidateID
    run_id: RunID
    market_snapshot_id: MarketSnapshotID
    candidate_source: str
    rank: int | None
    source_score: Decimal | None
    selected_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.candidate_id, CandidateID, "candidate_id")
        _require_instance(self.run_id, RunID, "run_id")
        _require_instance(self.market_snapshot_id, MarketSnapshotID, "market_snapshot_id")
        if self.rank is not None and (
            isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1
        ):
            raise ValidationError("rank must be at least one or None")
        _validate_optional_decimal(self.source_score, "source_score")
        object.__setattr__(
            self, "candidate_source", _normalize_code(self.candidate_source, "candidate_source")
        )
        object.__setattr__(self, "selected_at", normalize_utc(self.selected_at))


@dataclass(frozen=True, slots=True)
class StoredCandidate(NewCandidate):
    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredCandidate, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))


@dataclass(frozen=True, slots=True)
class NewFilterEvaluation:
    filter_evaluation_id: FilterEvaluationID
    candidate_id: CandidateID
    filter_set_id: FilterSetID
    evaluation_version: str
    passed: bool
    score: Decimal | None
    details: Mapping[str, JSONValue] = field(repr=False)
    evaluated_at: datetime

    def __post_init__(self) -> None:
        _require_instance(self.filter_evaluation_id, FilterEvaluationID, "filter_evaluation_id")
        _require_instance(self.candidate_id, CandidateID, "candidate_id")
        _require_instance(self.filter_set_id, FilterSetID, "filter_set_id")
        if not isinstance(self.passed, bool):
            raise ValidationError("passed must be a boolean")
        _validate_optional_decimal(self.score, "score")
        object.__setattr__(
            self,
            "evaluation_version",
            _normalize_code(self.evaluation_version, "evaluation_version"),
        )
        object.__setattr__(self, "details", freeze_json_object(self.details))
        object.__setattr__(self, "evaluated_at", normalize_utc(self.evaluated_at))


@dataclass(frozen=True, slots=True)
class StoredFilterEvaluation(NewFilterEvaluation):
    recorded_at: datetime

    def __post_init__(self) -> None:
        super(StoredFilterEvaluation, self).__post_init__()
        object.__setattr__(self, "recorded_at", normalize_utc(self.recorded_at))
