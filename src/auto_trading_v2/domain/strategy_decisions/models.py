"""Immutable models for deterministic strategy decisions."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import cast, overload

from auto_trading_v2.domain.filtering.models import FilterSetName
from auto_trading_v2.domain.primitives import FilterSetID, StrategyID
from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError
from auto_trading_v2.domain.strategy_decisions.reason_codes import (
    extract_blocking_reason_codes,
    normalize_reason_codes,
)


class StrategyName(StrEnum):
    STRICT_ENTRY = "STRICT_ENTRY"
    BALANCED_ENTRY = "BALANCED_ENTRY"
    SCORE_ONLY_ENTRY = "SCORE_ONLY_ENTRY"
    OBSERVATION_ONLY = "OBSERVATION_ONLY"


class StrategyAction(StrEnum):
    ENTER_LONG = "ENTER_LONG"
    SKIP = "SKIP"
    OBSERVE = "OBSERVE"


type StrategyJSONValue = (
    None | bool | int | str | Sequence[StrategyJSONValue] | Mapping[str, StrategyJSONValue]
)
type FrozenStrategyJSONValue = (
    None | bool | int | str | FrozenStrategyJSONList | Mapping[str, FrozenStrategyJSONValue]
)


@dataclass(frozen=True, slots=True)
class FrozenStrategyJSONList(Sequence[FrozenStrategyJSONValue]):
    """Deeply immutable representation of a JSON array."""

    _items: tuple[FrozenStrategyJSONValue, ...] = field(repr=False)

    @overload
    def __getitem__(self, index: int) -> FrozenStrategyJSONValue: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[FrozenStrategyJSONValue]: ...

    def __getitem__(
        self, index: int | slice
    ) -> FrozenStrategyJSONValue | Sequence[FrozenStrategyJSONValue]:
        return self._items[index]

    def __iter__(self) -> Iterator[FrozenStrategyJSONValue]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def freeze_strategy_json_object(
    value: Mapping[str, StrategyJSONValue],
) -> Mapping[str, StrategyJSONValue]:
    """Validate and deeply freeze a JSON object without echoing payloads."""

    if not isinstance(value, Mapping):
        raise StrategyValidationError("strategy details must be an object")
    return cast(Mapping[str, StrategyJSONValue], _freeze_mapping(value))


def _freeze_mapping(
    value: Mapping[str, object],
) -> Mapping[str, FrozenStrategyJSONValue]:
    frozen: dict[str, FrozenStrategyJSONValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise StrategyValidationError("strategy details keys must be strings")
        frozen[key] = _freeze_value(item)
    return MappingProxyType(frozen)


def _freeze_value(value: object) -> FrozenStrategyJSONValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return FrozenStrategyJSONList(tuple(_freeze_value(item) for item in value))
    raise StrategyValidationError("strategy details contain an unsupported value")


def validate_strategy_version(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 64:
        raise StrategyValidationError("strategy version is invalid")
    return value


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy_id: StrategyID
    name: StrategyName
    strategy_version: str
    source_filter_set_id: FilterSetID
    source_filter_set_name: FilterSetName
    source_evaluation_version: str
    observation_only: bool

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_id, StrategyID):
            raise StrategyValidationError("strategy_id has an invalid type")
        if not isinstance(self.name, StrategyName):
            raise StrategyValidationError("strategy name has an invalid type")
        object.__setattr__(
            self, "strategy_version", validate_strategy_version(self.strategy_version)
        )
        if not isinstance(self.source_filter_set_id, FilterSetID) or not isinstance(
            self.source_filter_set_name, FilterSetName
        ):
            raise StrategyValidationError("source filter identity is invalid")
        if (
            not isinstance(self.source_evaluation_version, str)
            or not self.source_evaluation_version.strip()
            or len(self.source_evaluation_version) > 64
        ):
            raise StrategyValidationError("source evaluation version is invalid")
        if not isinstance(self.observation_only, bool):
            raise StrategyValidationError("observation_only must be boolean")


@dataclass(frozen=True, slots=True)
class StrategySignal:
    filter_set_id: FilterSetID
    evaluation_version: str
    passed: bool
    score: Decimal
    details: Mapping[str, StrategyJSONValue] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.filter_set_id, FilterSetID):
            raise StrategyValidationError("filter_set_id has an invalid type")
        if not isinstance(self.evaluation_version, str) or not self.evaluation_version.strip():
            raise StrategyValidationError("evaluation_version must not be empty")
        if not isinstance(self.passed, bool):
            raise StrategyValidationError("passed must be boolean")
        if not isinstance(self.score, Decimal) or not self.score.is_finite():
            raise StrategyValidationError("score must be a finite Decimal")
        if self.score < 0 or self.score > 100:
            raise StrategyValidationError("score must be between 0 and 100")
        frozen = freeze_strategy_json_object(self.details)
        extract_blocking_reason_codes(frozen, require_non_empty=not self.passed)
        object.__setattr__(self, "details", frozen)


@dataclass(frozen=True, slots=True)
class StrategyDecisionResult:
    strategy_id: StrategyID
    strategy_name: StrategyName
    strategy_version: str
    source_filter_set_id: FilterSetID
    source_evaluation_version: str
    action: StrategyAction
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_id, StrategyID) or not isinstance(
            self.strategy_name, StrategyName
        ):
            raise StrategyValidationError("strategy result identity is invalid")
        object.__setattr__(
            self, "strategy_version", validate_strategy_version(self.strategy_version)
        )
        if not isinstance(self.source_filter_set_id, FilterSetID):
            raise StrategyValidationError("source_filter_set_id has an invalid type")
        if (
            not isinstance(self.source_evaluation_version, str)
            or not self.source_evaluation_version.strip()
        ):
            raise StrategyValidationError("source_evaluation_version must not be empty")
        if not isinstance(self.action, StrategyAction):
            raise StrategyValidationError("strategy action has an invalid type")
        if not isinstance(self.reason_codes, tuple):
            raise StrategyValidationError("reason codes must be a tuple")
        normalized = normalize_reason_codes(self.reason_codes)
        object.__setattr__(self, "reason_codes", normalized)
