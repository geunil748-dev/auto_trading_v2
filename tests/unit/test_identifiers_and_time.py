from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

import pytest

from auto_trading_v2.adapters.clock import FixedClock, SystemClock
from auto_trading_v2.domain.errors import InvalidTimestampError, ValidationError
from auto_trading_v2.domain.primitives.identifiers import (
    CandidateID,
    IdentifierFactory,
    StrategyID,
)
from auto_trading_v2.domain.primitives.time import SessionDate, UtcTimestamp


def test_typed_ids_round_trip_and_do_not_equal_other_id_types() -> None:
    raw = "12345678-1234-5678-1234-567812345678"
    strategy_id = StrategyID.parse(raw)
    candidate_id = CandidateID.parse(raw)

    assert strategy_id.serialize() == raw
    assert StrategyID.parse(strategy_id.serialize()) == strategy_id
    assert strategy_id != candidate_id
    assert len({strategy_id, StrategyID.parse(raw)}) == 1


def test_typed_id_rejects_invalid_uuid() -> None:
    with pytest.raises(ValidationError):
        StrategyID.parse("not-a-uuid")


def test_identifier_factory_uses_injected_generation_policy() -> None:
    expected = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    factory = IdentifierFactory(lambda: expected)

    assert factory.new(StrategyID) == StrategyID(expected)


def test_utc_timestamp_rejects_naive_and_normalizes_offset() -> None:
    with pytest.raises(InvalidTimestampError):
        UtcTimestamp(datetime(2026, 1, 2, 3, 4, 5))

    timestamp = UtcTimestamp(datetime(2026, 1, 2, 12, 4, 5, tzinfo=timezone(timedelta(hours=9))))

    assert timestamp.value == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert timestamp.serialize() == "2026-01-02T03:04:05Z"
    assert UtcTimestamp.parse(timestamp.serialize()) == timestamp


def test_session_date_round_trip_and_rejects_datetime() -> None:
    session_date = SessionDate(date(2026, 7, 13))

    assert session_date.serialize() == "2026-07-13"
    assert SessionDate.parse("2026-07-13") == session_date
    with pytest.raises(ValidationError):
        SessionDate(datetime(2026, 7, 13, tzinfo=UTC))


def test_system_clock_returns_aware_utc() -> None:
    now = SystemClock().now_utc()

    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)


def test_fixed_clock_changes_only_explicitly() -> None:
    initial = datetime(2026, 7, 13, tzinfo=UTC)
    clock = FixedClock(initial)

    assert clock.now_utc() == initial
    assert clock.now_utc() == initial
    clock.advance(timedelta(minutes=5))
    assert clock.now_utc() == initial + timedelta(minutes=5)
    clock.set(initial)
    assert clock.now_utc() == initial


def test_fixed_clock_rejects_naive_or_negative_changes() -> None:
    with pytest.raises(InvalidTimestampError):
        FixedClock(datetime(2026, 7, 13))

    clock = FixedClock(datetime(2026, 7, 13, tzinfo=UTC))
    with pytest.raises(ValidationError):
        clock.advance(timedelta(seconds=-1))
