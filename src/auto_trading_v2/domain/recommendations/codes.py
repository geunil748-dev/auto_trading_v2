"""Canonical technical-code collections for Recommendation facts."""

from __future__ import annotations

import re
from collections.abc import Sequence

from auto_trading_v2.domain.recommendations.errors import (
    RecommendationValidationError,
)

_CANONICAL_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_GENERATOR_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def canonical_codes(values: Sequence[str], label: str) -> tuple[str, ...]:
    """Validate, deduplicate, and sort a safe code collection."""

    if isinstance(values, str | bytes) or not isinstance(values, Sequence):
        raise RecommendationValidationError(f"{label}는 문자열 시퀀스여야 합니다.")
    if any(
        not isinstance(value, str) or not _CANONICAL_CODE_PATTERN.fullmatch(value)
        for value in values
    ):
        raise RecommendationValidationError(f"{label} 형식이 올바르지 않습니다.")
    if len(values) != len(set(values)):
        raise RecommendationValidationError(f"{label}에 중복 코드를 사용할 수 없습니다.")
    return tuple(sorted(values))


def normalize_generator_code(value: str, label: str) -> str:
    """Normalize a stable generator identity component."""

    if not isinstance(value, str):
        raise RecommendationValidationError(f"{label} 타입이 올바르지 않습니다.")
    normalized = value.strip()
    if not _GENERATOR_CODE_PATTERN.fullmatch(normalized):
        raise RecommendationValidationError(f"{label} 형식이 올바르지 않습니다.")
    return normalized
