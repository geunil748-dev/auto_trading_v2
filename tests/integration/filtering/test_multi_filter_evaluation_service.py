"""Real MSSQL multi-policy evaluation cases and details round-trip."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from auto_trading_v2.application.errors import CandidateNotFoundError
from auto_trading_v2.domain.filtering.catalog import BUILT_IN_FILTER_SETS
from auto_trading_v2.domain.filtering.models import FilterSetName
from auto_trading_v2.domain.primitives import CandidateID
from tests.integration.filtering.helpers import (
    EVALUATED_AT,
    evaluations_for,
    persist_candidate,
    service,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase

pytestmark = pytest.mark.integration


def _contains_decimal(value: object) -> bool:
    if isinstance(value, Decimal):
        return True
    if isinstance(value, Mapping):
        return any(_contains_decimal(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_decimal(item) for item in value)
    return False


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    values: dict[str, object]
    score: Decimal
    passed: tuple[bool, bool, bool, bool]


CASES = (
    Case(
        "all-pass",
        {
            "open_price": "22.66",
            "last_price": "25",
            "previous_high": "20",
            "previous_low": "10",
            "previous_close": "22",
        },
        Decimal("100"),
        (True, True, True, True),
    ),
    Case(
        "breakout-fails",
        {
            "open_price": "22.66",
            "last_price": "24",
            "previous_high": "20",
            "previous_low": "10",
            "previous_close": "22",
        },
        Decimal("70"),
        (False, True, True, True),
    ),
    Case(
        "previous-close-missing",
        {
            "open_price": "22.66",
            "last_price": "25",
            "previous_high": "20",
            "previous_low": "10",
            "previous_close": None,
        },
        Decimal("60"),
        (False, False, True, True),
    ),
    Case(
        "price-range-fails",
        {
            "open_price": "309",
            "last_price": "301",
            "previous_high": "200",
            "previous_low": "100",
            "previous_close": "300",
            "current_high": "310",
            "current_low": "250",
        },
        Decimal("80"),
        (False, False, True, True),
    ),
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_case_matrix_persists_four_atomic_evaluations(
    mssql_database: TemporaryMssqlDatabase,
    case: Case,
) -> None:
    candidate_id = persist_candidate(mssql_database.engine, **case.values)  # type: ignore[arg-type]

    batch = service(mssql_database.engine).evaluate_all(candidate_id)

    assert len(batch.evaluations) == 4
    assert tuple(item.filter_set_id for item in batch.evaluations) == tuple(
        definition.filter_set_id for definition in BUILT_IN_FILTER_SETS
    )
    assert tuple(item.evaluation_version for item in batch.evaluations) == ("v1",) * 4
    assert tuple(item.score for item in batch.evaluations) == (case.score,) * 4
    assert tuple(item.passed for item in batch.evaluations) == case.passed
    assert {item.evaluated_at for item in batch.evaluations} == {EVALUATED_AT}
    persisted = evaluations_for(mssql_database.engine, candidate_id)
    assert len(persisted) == 4
    assert {item.filter_set_id for item in persisted} == {
        definition.filter_set_id for definition in BUILT_IN_FILTER_SETS
    }


def test_details_round_trip_has_canonical_shape_and_no_entity_copy(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = persist_candidate(
        mssql_database.engine,
        open_price="22.66",
        last_price="24",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )

    batch = service(mssql_database.engine).evaluate_all(candidate_id)
    balanced = next(
        item
        for item in batch.evaluations
        if item.filter_set_id
        == next(
            definition.filter_set_id
            for definition in BUILT_IN_FILTER_SETS
            if definition.name is FilterSetName.BALANCED
        )
    )
    details = cast(Mapping[str, object], balanced.details)

    assert details["schema_version"] == "filter-evaluation-details/v1"
    assert details["filter_set_name"] == "BALANCED"
    assert details["counts"] == {"pass": 4, "fail": 1, "not_evaluable": 0}
    assert not {"candidate_id", "market_snapshot", "symbol", "passed", "score"}.intersection(
        details
    )
    checks = cast(Sequence[Mapping[str, object]], details["checks"])
    assert len(checks) == 5
    assert not _contains_decimal(details)
    first_observed = cast(Mapping[str, object], checks[0]["observed"])
    assert first_observed["last_price"] == "24.000000000000000000"


def test_missing_candidate_writes_nothing(mssql_database: TemporaryMssqlDatabase) -> None:
    candidate_id = CandidateID(uuid4())

    with pytest.raises(CandidateNotFoundError):
        service(mssql_database.engine).evaluate_all(candidate_id)

    assert evaluations_for(mssql_database.engine, candidate_id) == ()
