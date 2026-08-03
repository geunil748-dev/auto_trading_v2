from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from auto_trading_v2.application.contracts.persistence import (
    NewCandidate,
    NewFilterEvaluation,
    NewMarketSnapshot,
    StoredMarketSnapshot,
)
from auto_trading_v2.config import SecretValue
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


def _snapshot(**changes: object) -> NewMarketSnapshot:
    values: dict[str, object] = {
        "market_snapshot_id": MarketSnapshotID(uuid4()),
        "symbol": Symbol("AAPL"),
        "session_date": SessionDate(date(2026, 7, 14)),
        "observed_at": datetime(2026, 7, 14, 9, tzinfo=timezone(timedelta(hours=9))),
        "source": " MARKET ",
        "open_price": Price(Decimal("100")),
        "high_price": Price(Decimal("102")),
        "low_price": Price(Decimal("99")),
        "last_price": Price(Decimal("101")),
        "previous_high_price": Price(Decimal("103")),
        "previous_low_price": Price(Decimal("98")),
        "previous_close_price": None,
        "volume": 0,
    }
    values.update(changes)
    return NewMarketSnapshot(**values)  # type: ignore[arg-type]


def _candidate(**changes: object) -> NewCandidate:
    values: dict[str, object] = {
        "candidate_id": CandidateID(uuid4()),
        "run_id": RunID(uuid4()),
        "market_snapshot_id": MarketSnapshotID(uuid4()),
        "candidate_source": "RANKING",
        "rank": None,
        "source_score": Decimal("1.25"),
        "selected_at": datetime(2026, 7, 14, tzinfo=UTC),
    }
    values.update(changes)
    return NewCandidate(**values)  # type: ignore[arg-type]


def _evaluation(details: object) -> NewFilterEvaluation:
    return NewFilterEvaluation(
        filter_evaluation_id=FilterEvaluationID(uuid4()),
        candidate_id=CandidateID(uuid4()),
        filter_set_id=FilterSetID(uuid4()),
        evaluation_version="v1",
        passed=True,
        score=Decimal("0.75"),
        details=details,  # type: ignore[arg-type]
        evaluated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )


def test_market_contract_normalizes_codes_and_utc() -> None:
    snapshot = _snapshot()

    assert snapshot.source == "MARKET"
    assert snapshot.observed_at == datetime(2026, 7, 14, tzinfo=UTC)

    stored = StoredMarketSnapshot(
        **{field.name: getattr(snapshot, field.name) for field in fields(snapshot)},
        recorded_at=datetime(2026, 7, 14, 1, tzinfo=UTC),
    )
    assert stored.recorded_at.tzinfo is UTC
    with pytest.raises(FrozenInstanceError):
        stored.source = "OTHER"  # type: ignore[misc]


@pytest.mark.parametrize("volume", [-1, True, 1.5])
def test_market_contract_rejects_invalid_volume(volume: object) -> None:
    with pytest.raises(ValidationError):
        _snapshot(volume=volume)


def test_contracts_reject_naive_time_empty_codes_and_float_decimal() -> None:
    with pytest.raises(ValidationError):
        _snapshot(observed_at=datetime(2026, 7, 14))
    with pytest.raises(ValidationError):
        _snapshot(source=" ")
    with pytest.raises(ValidationError):
        _candidate(candidate_source="")
    with pytest.raises(ValidationError):
        _candidate(source_score=1.25)


@pytest.mark.parametrize("rank", [0, -1, True, 1.5])
def test_candidate_contract_rejects_invalid_rank(rank: object) -> None:
    with pytest.raises(ValidationError):
        _candidate(rank=rank)


def test_filter_details_are_deeply_copied_and_immutable() -> None:
    original: dict[str, object] = {
        "한글": "보존",
        "nested": {"items": [1, True, None]},
    }
    evaluation = _evaluation(original)
    original["한글"] = "변경"
    nested = original["nested"]
    assert isinstance(nested, dict)
    nested["items"] = []

    assert evaluation.details["한글"] == "보존"
    frozen_nested = evaluation.details["nested"]
    assert isinstance(frozen_nested, dict) is False
    with pytest.raises(TypeError):
        evaluation.details["new"] = 1  # type: ignore[index]

    copied = replace(evaluation, evaluation_version="v2")
    assert copied.details == evaluation.details


@pytest.mark.parametrize(
    "unsupported",
    [
        1.5,
        Decimal("1"),
        datetime(2026, 7, 14, tzinfo=UTC),
        UUID(int=1),
        SecretValue("secret"),
        b"bytes",
        {"set"},
        (1, 2),
        object(),
    ],
)
def test_filter_details_reject_unsupported_values_without_echoing_them(
    unsupported: object,
) -> None:
    with pytest.raises(ValidationError) as caught:
        _evaluation({"payload": unsupported})

    assert "payload" not in str(caught.value)
    assert "secret" not in str(caught.value)


def test_filter_details_require_a_top_level_object() -> None:
    with pytest.raises(ValidationError):
        _evaluation([1, 2])
