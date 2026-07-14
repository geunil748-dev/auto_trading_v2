from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.config import SecretValue
from auto_trading_v2.domain.filtering.catalog import BALANCED
from auto_trading_v2.domain.filtering.details import (
    SCHEMA_VERSION,
    build_filter_evaluation_details,
    serialize_filter_evaluation_details,
)
from auto_trading_v2.domain.filtering.engine import DeterministicFilterEngine
from auto_trading_v2.domain.filtering.errors import FilterValidationError
from auto_trading_v2.domain.filtering.models import FilterCheckResult, FilterOutcome

from .helpers import filter_input

SENTINEL = "SHOULD_NEVER_APPEAR_PR5_4d901f"


def test_details_have_canonical_shape_without_duplicate_entities() -> None:
    result = DeterministicFilterEngine().evaluate(filter_input(last_price="24"), BALANCED)
    details = build_filter_evaluation_details(result)

    assert details["schema_version"] == SCHEMA_VERSION
    assert details["filter_set_name"] == "BALANCED"
    assert details["mode"] == "BALANCED"
    assert details["counts"] == {"pass": 4, "fail": 1, "not_evaluable": 0}
    assert details["blocking_reason_codes"] == []
    assert "candidate_id" not in details
    assert "market_snapshot" not in details
    assert "symbol" not in details
    assert "passed" not in details
    assert "score" not in details


def test_details_decimal_values_are_fixed_point_and_json_is_compact_stable_unicode() -> None:
    result = DeterministicFilterEngine().evaluate(filter_input(), BALANCED)
    first = result.checks[0]
    unicode_check = replace(first, observed={"note": "한글", "decimal": "0.000000000000000001"})
    result = replace(result, checks=(unicode_check, *result.checks[1:]))

    serialized = serialize_filter_evaluation_details(result)

    assert "한글" in serialized
    assert " " not in serialized
    assert "0.000000000000000001" in serialized
    assert "E-" not in serialized
    assert serialized == serialize_filter_evaluation_details(result)


@pytest.mark.parametrize(
    "unsupported",
    [
        1.5,
        Decimal("1"),
        datetime(2026, 7, 14, tzinfo=UTC),
        UUID(int=1),
        SecretValue(SENTINEL),
        b"bytes",
        {"set"},
        (1, 2),
        object(),
    ],
)
def test_check_details_reject_unsupported_payload_without_exposure(
    unsupported: object,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(FilterValidationError) as caught:
        FilterCheckResult(
            name=next(iter(BALANCED.hard_checks)),
            outcome=FilterOutcome.PASS,
            reason_code="SAFE_REASON",
            hard=True,
            weight=Decimal("20"),
            observed={"unsafe": unsupported},  # type: ignore[dict-item]
            threshold={},
        )

    captured = capsys.readouterr()
    assert SENTINEL not in str(caught.value)
    assert SENTINEL not in repr(caught.value)
    assert SENTINEL not in captured.out
    assert SENTINEL not in captured.err
