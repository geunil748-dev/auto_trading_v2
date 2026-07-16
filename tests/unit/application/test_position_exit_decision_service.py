from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from inspect import signature
from uuid import UUID

import pytest

from auto_trading_v2.application.contracts.position_exit_decisions import (
    PositionExitDecisionOutcome,
)
from auto_trading_v2.application.position_exit_errors import (
    PositionExitPositionNotFoundError,
    PositionExitSnapshotNotFoundError,
    PositionExitSourceError,
    UnsupportedPositionExitCurrencyError,
)
from auto_trading_v2.application.services.position_exit_decision import (
    PositionExitDecisionService,
)
from auto_trading_v2.domain.position_projection import PaperPositionStatus
from auto_trading_v2.domain.primitives import (
    Currency,
    Money,
    Price,
    Quantity,
    StrategyID,
    Symbol,
)
from auto_trading_v2.domain.strategy_decisions import StrategyAction
from auto_trading_v2.domain.strategy_decisions.catalog import OBSERVATION_ONLY

from .position_exit_fakes import (
    FakeUnitOfWork,
    assert_no_write,
    service_for,
)
from .position_exit_records import (
    NOW,
    POSITION_ID,
    SNAPSHOT_ID,
    entry_decision,
    event,
    position,
    snapshot,
)


def test_public_input_is_only_position_and_snapshot_ids() -> None:
    assert tuple(signature(PositionExitDecisionService.decide).parameters) == (
        "self",
        "position_id",
        "market_snapshot_id",
    )


def test_open_position_creates_skip_decision_pinned_to_version() -> None:
    unit_of_work = FakeUnitOfWork()
    service, _, clock, ids = service_for(unit_of_work)

    result = service.decide(POSITION_ID, SNAPSHOT_ID)

    assert result.outcome is PositionExitDecisionOutcome.CREATED
    assert result.position_version == 1
    assert result.action is StrategyAction.SKIP
    assert result.reason_codes == ("EXIT_CONDITIONS_NOT_MET", "POSITION_HOLD")
    assert result.return_rate is not None and result.return_rate.value == Decimal("0")
    assert unit_of_work.commit_calls == ids.calls == clock.calls == 1


def test_closed_position_is_rejected_without_write() -> None:
    closed = position(
        status=PaperPositionStatus.CLOSED,
        quantity=Quantity(0),
        closed_at=NOW,
    )
    unit_of_work = FakeUnitOfWork(stored_position=closed)
    service, _, _, ids = service_for(unit_of_work)

    with pytest.raises(PositionExitSourceError, match="position_not_open"):
        service.decide(POSITION_ID, SNAPSHOT_ID)

    assert_no_write(unit_of_work, ids)


def test_missing_position_and_snapshot_are_explicit() -> None:
    missing_position = FakeUnitOfWork()
    missing_position.paper_positions.value = None
    service, _, _, ids = service_for(missing_position)
    with pytest.raises(PositionExitPositionNotFoundError):
        service.decide(POSITION_ID, SNAPSHOT_ID)
    assert_no_write(missing_position, ids)

    missing_snapshot = FakeUnitOfWork()
    missing_snapshot.market_snapshots.value = None
    service, _, _, ids = service_for(missing_snapshot)
    with pytest.raises(PositionExitSnapshotNotFoundError):
        service.decide(POSITION_ID, SNAPSHOT_ID)
    assert_no_write(missing_snapshot, ids)


def test_symbol_and_currency_boundaries_are_rejected() -> None:
    symbol_mismatch = FakeUnitOfWork(
        stored_snapshot=snapshot(symbol=Symbol("MSFT")),
    )
    service, _, _, ids = service_for(symbol_mismatch)
    with pytest.raises(PositionExitSourceError, match="symbol_mismatch"):
        service.decide(POSITION_ID, SNAPSHOT_ID)
    assert_no_write(symbol_mismatch, ids)

    eur = Currency("EUR")
    unsupported = FakeUnitOfWork(
        stored_position=position(
            currency=eur,
            realized_pnl=Money(Decimal("0"), eur),
        ),
        stored_intent=replace(
            FakeUnitOfWork().trade_intents.value,
            currency=eur,
        ),
        stored_event=event(
            realized_pnl_delta=Money(Decimal("0"), eur),
            realized_pnl_after=Money(Decimal("0"), eur),
        ),
    )
    service, _, _, ids = service_for(unsupported)
    with pytest.raises(UnsupportedPositionExitCurrencyError):
        service.decide(POSITION_ID, SNAPSHOT_ID)
    assert_no_write(unsupported, ids)


def test_snapshot_must_not_precede_position_update() -> None:
    source = FakeUnitOfWork(
        stored_snapshot=snapshot(observed_at=NOW - timedelta(minutes=2)),
    )
    service, _, _, ids = service_for(source)

    with pytest.raises(PositionExitSourceError, match="snapshot_precedes_position"):
        service.decide(POSITION_ID, SNAPSHOT_ID)

    assert_no_write(source, ids)


@pytest.mark.parametrize(
    ("observed_delta", "allowed", "reason"),
    [
        (timedelta(minutes=-5), True, None),
        (timedelta(minutes=-5, microseconds=-1), False, "snapshot_stale"),
        (timedelta(seconds=30), True, None),
        (timedelta(seconds=30, microseconds=1), False, "snapshot_too_far_in_future"),
    ],
)
def test_snapshot_freshness_boundaries(
    observed_delta: timedelta,
    allowed: bool,
    reason: str | None,
) -> None:
    observed_at = NOW + observed_delta
    source = FakeUnitOfWork(
        stored_position=position(updated_at=NOW - timedelta(minutes=6)),
        stored_event=event(occurred_at=NOW - timedelta(minutes=6)),
        stored_fill=replace(
            FakeUnitOfWork().paper_fills.value, executed_at=NOW - timedelta(minutes=6)
        ),
        stored_snapshot=snapshot(observed_at=observed_at),
    )
    service, _, _, ids = service_for(source)

    if allowed:
        assert (
            service.decide(POSITION_ID, SNAPSHOT_ID).outcome is PositionExitDecisionOutcome.CREATED
        )
    else:
        with pytest.raises(PositionExitSourceError, match=reason or ""):
            service.decide(POSITION_ID, SNAPSHOT_ID)
        assert_no_write(source, ids)


@pytest.mark.parametrize(
    ("stored_event", "reason"),
    [
        (None, "position_event_missing"),
        (
            event(quantity_delta=Quantity(9), quantity_after=Quantity(9)),
            "position_event_mismatch",
        ),
        (event(average_cost_after=Price(Decimal("99"))), "position_event_mismatch"),
    ],
)
def test_position_event_version_and_state_must_match(
    stored_event,
    reason: str,
) -> None:
    source = FakeUnitOfWork()
    source.position_events.value = stored_event
    service, _, _, ids = service_for(source)

    with pytest.raises(PositionExitSourceError, match=reason):
        service.decide(POSITION_ID, SNAPSHOT_ID)

    assert_no_write(source, ids)


def test_strategy_mismatch_and_unsupported_versions_are_rejected() -> None:
    other = StrategyID(UUID(int=100))
    mismatch = FakeUnitOfWork(
        stored_position=position(strategy_id=other),
    )
    service, _, _, ids = service_for(mismatch)
    with pytest.raises(PositionExitSourceError, match="strategy_source_mismatch"):
        service.decide(POSITION_ID, SNAPSHOT_ID)
    assert_no_write(mismatch, ids)

    unsupported = FakeUnitOfWork(
        stored_position=position(strategy_id=other),
        stored_entry_decision=entry_decision(strategy_id=other),
    )
    service, _, _, ids = service_for(unsupported)
    with pytest.raises(PositionExitSourceError, match="unsupported_strategy_version"):
        service.decide(POSITION_ID, SNAPSHOT_ID)
    assert_no_write(unsupported, ids)


def test_observation_strategy_is_not_exit_eligible() -> None:
    source = FakeUnitOfWork(
        stored_position=position(strategy_id=OBSERVATION_ONLY.strategy_id),
        stored_entry_decision=entry_decision(
            strategy_id=OBSERVATION_ONLY.strategy_id,
            action=StrategyAction.OBSERVE,
        ),
    )
    service, _, _, ids = service_for(source)

    with pytest.raises(PositionExitSourceError, match="unsupported_strategy_version"):
        service.decide(POSITION_ID, SNAPSHOT_ID)

    assert_no_write(source, ids)
