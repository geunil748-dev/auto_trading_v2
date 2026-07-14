"""Immutable models for pure multi-filter evaluation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import cast, overload

from auto_trading_v2.domain.filtering.errors import FilterValidationError
from auto_trading_v2.domain.primitives import FilterSetID, Price, Symbol


class FilterCheckName(StrEnum):
    PRICE_RANGE = "PRICE_RANGE"
    OPENING_CHANGE_MIN = "OPENING_CHANGE_MIN"
    ENTRY_CHANGE_MAX = "ENTRY_CHANGE_MAX"
    BREAKOUT_TRIGGERED = "BREAKOUT_TRIGGERED"
    VOLUME_PRESENT = "VOLUME_PRESENT"


class FilterOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class FilterSetName(StrEnum):
    STRICT = "STRICT"
    BALANCED = "BALANCED"
    SCORE_ONLY = "SCORE_ONLY"
    OBSERVATION = "OBSERVATION"


class FilterMode(StrEnum):
    STRICT = "STRICT"
    BALANCED = "BALANCED"
    SCORE_ONLY = "SCORE_ONLY"
    OBSERVATION = "OBSERVATION"


CHECK_ORDER = tuple(FilterCheckName)

type FilterJSONValue = (
    None | bool | int | str | list[FilterJSONValue] | Mapping[str, FilterJSONValue]
)
type FrozenFilterJSONValue = (
    None | bool | int | str | FrozenFilterJSONList | Mapping[str, FrozenFilterJSONValue]
)


@dataclass(frozen=True, slots=True)
class FrozenFilterJSONList(Sequence[FrozenFilterJSONValue]):
    """Deeply immutable internal form of an accepted JSON list."""

    _items: tuple[FrozenFilterJSONValue, ...] = field(repr=False)

    @overload
    def __getitem__(self, index: int) -> FrozenFilterJSONValue: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[FrozenFilterJSONValue]: ...

    def __getitem__(
        self, index: int | slice
    ) -> FrozenFilterJSONValue | Sequence[FrozenFilterJSONValue]:
        return self._items[index]

    def __iter__(self) -> Iterator[FrozenFilterJSONValue]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def freeze_filter_json_object(
    value: Mapping[str, FilterJSONValue],
) -> Mapping[str, FilterJSONValue]:
    """Return a validated deeply immutable copy without echoing payloads in errors."""

    if not isinstance(value, Mapping):
        raise FilterValidationError("filter JSON must be an object")
    return cast(Mapping[str, FilterJSONValue], _freeze_mapping(value))


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, FrozenFilterJSONValue]:
    frozen: dict[str, FrozenFilterJSONValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise FilterValidationError("filter JSON keys must be strings")
        frozen[key] = _freeze_value(item)
    return MappingProxyType(frozen)


def _freeze_value(value: object) -> FrozenFilterJSONValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, FrozenFilterJSONList):
        return FrozenFilterJSONList(tuple(_freeze_value(item) for item in value))
    if isinstance(value, list):
        return FrozenFilterJSONList(tuple(_freeze_value(item) for item in value))
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    raise FilterValidationError("filter JSON contains an unsupported value")


def _finite_decimal(value: Decimal, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise FilterValidationError(f"{label} must be a finite Decimal")
    return value


@dataclass(frozen=True, slots=True)
class FilterInput:
    symbol: Symbol
    open_price: Price
    last_price: Price
    previous_high_price: Price
    previous_low_price: Price
    previous_close_price: Price | None
    volume: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise FilterValidationError("symbol has an invalid type")
        for name in (
            "open_price",
            "last_price",
            "previous_high_price",
            "previous_low_price",
        ):
            if not isinstance(getattr(self, name), Price):
                raise FilterValidationError(f"{name} has an invalid type")
        if self.previous_close_price is not None and not isinstance(
            self.previous_close_price, Price
        ):
            raise FilterValidationError("previous_close_price has an invalid type")
        if self.volume is not None and (
            isinstance(self.volume, bool) or not isinstance(self.volume, int) or self.volume < 0
        ):
            raise FilterValidationError("volume must be a non-negative integer or None")


@dataclass(frozen=True, slots=True)
class FilterThresholds:
    minimum_price: Price
    maximum_price: Price
    minimum_opening_change: Decimal
    maximum_entry_change: Decimal
    breakout_factor: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.minimum_price, Price) or not isinstance(self.maximum_price, Price):
            raise FilterValidationError("price thresholds must use Price")
        if self.minimum_price.value > self.maximum_price.value:
            raise FilterValidationError("price threshold range is invalid")
        for name in (
            "minimum_opening_change",
            "maximum_entry_change",
            "breakout_factor",
        ):
            value = _finite_decimal(getattr(self, name), name)
            if value < 0:
                raise FilterValidationError(f"{name} must not be negative")


@dataclass(frozen=True, slots=True)
class FilterCheckWeight:
    name: FilterCheckName
    weight: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.name, FilterCheckName):
            raise FilterValidationError("check weight name is invalid")
        if _finite_decimal(self.weight, "weight") < 0:
            raise FilterValidationError("weight must not be negative")


@dataclass(frozen=True, slots=True)
class FilterSetDefinition:
    filter_set_id: FilterSetID
    name: FilterSetName
    evaluation_version: str
    mode: FilterMode
    thresholds: FilterThresholds
    weights: tuple[FilterCheckWeight, ...]
    hard_checks: tuple[FilterCheckName, ...]
    minimum_score: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.filter_set_id, FilterSetID):
            raise FilterValidationError("filter_set_id has an invalid type")
        if not isinstance(self.name, FilterSetName) or not isinstance(self.mode, FilterMode):
            raise FilterValidationError("filter set name or mode is invalid")
        if not isinstance(self.evaluation_version, str) or not self.evaluation_version.strip():
            raise FilterValidationError("evaluation_version must not be empty")
        if not isinstance(self.thresholds, FilterThresholds):
            raise FilterValidationError("thresholds have an invalid type")
        if not isinstance(self.weights, tuple) or any(
            not isinstance(item, FilterCheckWeight) for item in self.weights
        ):
            raise FilterValidationError("check weights have an invalid type")
        if tuple(item.name for item in self.weights) != CHECK_ORDER:
            raise FilterValidationError("check weights must follow canonical order")
        if sum((item.weight for item in self.weights), Decimal("0")) != Decimal("100"):
            raise FilterValidationError("check weights must total 100")
        if not isinstance(self.hard_checks, tuple) or any(
            not isinstance(item, FilterCheckName) for item in self.hard_checks
        ):
            raise FilterValidationError("hard checks have an invalid type")
        if len(set(self.hard_checks)) != len(self.hard_checks):
            raise FilterValidationError("hard checks must be unique")
        if any(name not in CHECK_ORDER for name in self.hard_checks):
            raise FilterValidationError("hard check is unknown")
        minimum = _finite_decimal(self.minimum_score, "minimum_score")
        if minimum < 0 or minimum > 100:
            raise FilterValidationError("minimum_score must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class FilterCheckResult:
    name: FilterCheckName
    outcome: FilterOutcome
    reason_code: str
    hard: bool
    weight: Decimal
    observed: Mapping[str, FilterJSONValue] = field(repr=False)
    threshold: Mapping[str, FilterJSONValue] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, FilterCheckName) or not isinstance(
            self.outcome, FilterOutcome
        ):
            raise FilterValidationError("check result identity is invalid")
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise FilterValidationError("reason_code must not be empty")
        if not isinstance(self.hard, bool):
            raise FilterValidationError("hard must be boolean")
        if _finite_decimal(self.weight, "weight") < 0:
            raise FilterValidationError("weight must not be negative")
        object.__setattr__(self, "observed", freeze_filter_json_object(self.observed))
        object.__setattr__(self, "threshold", freeze_filter_json_object(self.threshold))


@dataclass(frozen=True, slots=True)
class FilterEvaluationResult:
    filter_set_id: FilterSetID
    filter_set_name: FilterSetName
    evaluation_version: str
    mode: FilterMode
    passed: bool
    score: Decimal
    checks: tuple[FilterCheckResult, ...]
    blocking_reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.filter_set_id, FilterSetID):
            raise FilterValidationError("filter_set_id has an invalid type")
        if not isinstance(self.filter_set_name, FilterSetName) or not isinstance(
            self.mode, FilterMode
        ):
            raise FilterValidationError("filter evaluation identity is invalid")
        if not isinstance(self.evaluation_version, str) or not self.evaluation_version.strip():
            raise FilterValidationError("evaluation_version must not be empty")
        if not isinstance(self.checks, tuple) or any(
            not isinstance(check, FilterCheckResult) for check in self.checks
        ):
            raise FilterValidationError("evaluation checks have an invalid type")
        if tuple(check.name for check in self.checks) != CHECK_ORDER:
            raise FilterValidationError("evaluation checks must follow canonical order")
        score = _finite_decimal(self.score, "score")
        if score < 0 or score > 100:
            raise FilterValidationError("score must be between 0 and 100")
        if not isinstance(self.passed, bool):
            raise FilterValidationError("passed must be boolean")
        if not isinstance(self.blocking_reason_codes, tuple):
            raise FilterValidationError("blocking reason codes have an invalid type")
        if any(not isinstance(code, str) or not code for code in self.blocking_reason_codes):
            raise FilterValidationError("blocking reason code is invalid")
