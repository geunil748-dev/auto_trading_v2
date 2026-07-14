"""Deterministic JSON-ready filter evaluation details."""

from __future__ import annotations

import json

from auto_trading_v2.domain.filtering.models import (
    FilterEvaluationResult,
    FilterJSONValue,
    FilterOutcome,
)

SCHEMA_VERSION = "filter-evaluation-details/v1"


def build_filter_evaluation_details(
    result: FilterEvaluationResult,
) -> dict[str, FilterJSONValue]:
    """Build the non-duplicative canonical details object."""

    counts = {
        "pass": sum(check.outcome is FilterOutcome.PASS for check in result.checks),
        "fail": sum(check.outcome is FilterOutcome.FAIL for check in result.checks),
        "not_evaluable": sum(
            check.outcome is FilterOutcome.NOT_EVALUABLE for check in result.checks
        ),
    }
    checks: list[FilterJSONValue] = [
        {
            "name": check.name.value,
            "outcome": check.outcome.value,
            "reason_code": check.reason_code,
            "hard": check.hard,
            "weight": int(check.weight),
            "observed": dict(check.observed),
            "threshold": dict(check.threshold),
        }
        for check in result.checks
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "filter_set_name": result.filter_set_name.value,
        "mode": result.mode.value,
        "counts": counts,
        "blocking_reason_codes": list(result.blocking_reason_codes),
        "checks": checks,
    }


def serialize_filter_evaluation_details(result: FilterEvaluationResult) -> str:
    """Serialize details with stable Unicode-preserving compact JSON."""

    return json.dumps(
        build_filter_evaluation_details(result),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
