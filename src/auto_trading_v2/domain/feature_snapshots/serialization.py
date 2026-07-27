"""Deterministic, deeply immutable JSON handling for feature values."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any, overload

from auto_trading_v2.domain.feature_snapshots.errors import (
    FeatureSnapshotValidationError,
)

type CanonicalJSONValue = (
    None | bool | int | str | FrozenFeatureList | Mapping[str, CanonicalJSONValue]
)

_FORBIDDEN_FEATURE_KEYS = frozenset(
    {
        "actual_result",
        "future_price",
        "future_prices",
        "future_return",
        "future_returns",
        "label",
        "labels",
        "outcome",
        "outcomes",
        "prediction",
        "predictions",
        "recommendation",
        "recommendations",
        "target",
        "target_label",
        "virtual_result",
    }
)


@dataclass(frozen=True, slots=True)
class FrozenFeatureList(Sequence[CanonicalJSONValue]):
    """Immutable internal representation of an accepted JSON list."""

    _items: tuple[CanonicalJSONValue, ...] = field(repr=False)

    @overload
    def __getitem__(self, index: int) -> CanonicalJSONValue: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[CanonicalJSONValue]: ...

    def __getitem__(self, index: int | slice) -> CanonicalJSONValue | Sequence[CanonicalJSONValue]:
        return self._items[index]

    def __iter__(self) -> Iterator[CanonicalJSONValue]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def canonicalize_feature_values(
    value: Mapping[str, object],
) -> Mapping[str, CanonicalJSONValue]:
    """Validate and freeze a non-empty top-level feature JSON object."""

    if not isinstance(value, Mapping) or not value:
        raise FeatureSnapshotValidationError(
            "feature_values는 비어 있지 않은 JSON 객체여야 합니다."
        )
    return _freeze_mapping(value)


def canonical_json(value: object) -> str:
    """Serialize accepted canonical values as compact, sorted Unicode JSON."""

    ready = _plain_json(value)
    return json.dumps(ready, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def plain_json(value: object) -> object:
    """Return a mutable JSON-compatible copy for persistence boundaries."""

    return _plain_json(value)


def _freeze_mapping(value: Mapping[Any, object]) -> Mapping[str, CanonicalJSONValue]:
    if any(not isinstance(key, str) for key in value):
        raise FeatureSnapshotValidationError("feature_values의 모든 키는 문자열이어야 합니다.")
    frozen: dict[str, CanonicalJSONValue] = {}
    for key in sorted(value):
        if not isinstance(key, str):
            raise FeatureSnapshotValidationError("feature_values의 모든 키는 문자열이어야 합니다.")
        if key.casefold() in _FORBIDDEN_FEATURE_KEYS:
            raise FeatureSnapshotValidationError(
                "feature_values에는 미래 결과나 추천 결과 필드를 저장할 수 없습니다."
            )
        frozen[key] = _freeze_value(value[key])
    return MappingProxyType(frozen)


def _freeze_value(value: object) -> CanonicalJSONValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise FeatureSnapshotValidationError("Decimal feature 값은 유한해야 합니다.")
        if value == 0:
            return "0"
        return format(value.normalize(), "f")
    if isinstance(value, float):
        raise FeatureSnapshotValidationError("Python float feature 값은 허용되지 않습니다.")
    if isinstance(value, list):
        return FrozenFeatureList(tuple(_freeze_value(item) for item in value))
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    raise FeatureSnapshotValidationError("지원되지 않는 feature JSON 값입니다.")


def _plain_json(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, FrozenFeatureList):
        return [_plain_json(item) for item in value]
    if isinstance(value, list | tuple):
        return [_plain_json(item) for item in value]
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise FeatureSnapshotValidationError("canonical JSON 키는 문자열이어야 합니다.")
        return {key: _plain_json(value[key]) for key in sorted(value)}
    raise FeatureSnapshotValidationError("canonical JSON으로 직렬화할 수 없는 값입니다.")
