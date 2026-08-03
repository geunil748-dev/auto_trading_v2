"""Canonical strategy-decision reason-code validation."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from auto_trading_v2.domain.strategy_decisions.errors import StrategyValidationError

REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
MAX_BLOCKING_REASON_CODES = 16


def validate_reason_code(value: object) -> str:
    """Return one canonical code without including rejected input in errors."""

    if not isinstance(value, str) or REASON_CODE_PATTERN.fullmatch(value) is None:
        raise StrategyValidationError("reason code is invalid")
    return value


def normalize_reason_codes(
    values: Sequence[object],
    *,
    require_non_empty: bool = True,
    maximum: int | None = None,
    deduplicate: bool = False,
) -> tuple[str, ...]:
    """Validate ordered reason codes with an explicit duplicate policy."""

    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise StrategyValidationError("reason codes must be an array")
    if maximum is not None and len(values) > maximum:
        raise StrategyValidationError("too many reason codes")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        code = validate_reason_code(item)
        if code in seen:
            if deduplicate:
                continue
            raise StrategyValidationError("reason codes must be unique")
        seen.add(code)
        normalized.append(code)
    if require_non_empty and not normalized:
        raise StrategyValidationError("reason codes must not be empty")
    return tuple(normalized)


def extract_blocking_reason_codes(
    details: Mapping[str, object],
    *,
    require_non_empty: bool,
) -> tuple[str, ...]:
    """Read only the validated blocking-code array without exposing details."""

    if "blocking_reason_codes" not in details:
        raise StrategyValidationError("blocking reason codes are missing")
    raw = details["blocking_reason_codes"]
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise StrategyValidationError("blocking reason codes must be an array")
    return normalize_reason_codes(
        raw,
        require_non_empty=require_non_empty,
        maximum=MAX_BLOCKING_REASON_CODES,
        deduplicate=True,
    )
