"""Real MSSQL deterministic EXIT_LONG and idempotency behavior."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import update

from auto_trading_v2.adapters.persistence.tables import paper_positions
from auto_trading_v2.application.contracts.position_exit_decisions import (
    PositionExitDecisionOutcome,
)
from auto_trading_v2.application.position_exit_errors import PositionExitSourceError
from auto_trading_v2.domain.strategy_decisions import StrategyAction
from auto_trading_v2.domain.strategy_decisions.catalog import OBSERVATION_ONLY
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.position_exit_decisions.helpers import (
    add_snapshot,
    decisions_for,
    position_row,
    prepare_position,
    service,
    source_counts,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("last_price", "reason"),
    [
        ("110", "TAKE_PROFIT_TRIGGERED"),
        ("95", "STOP_LOSS_TRIGGERED"),
    ],
)
def test_price_thresholds_create_exit_long(
    mssql_database: TemporaryMssqlDatabase,
    last_price: str,
    reason: str,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.updated_at + timedelta(minutes=1)
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price=last_price,
    )

    result = service(mssql_database.engine, observed_at).decide(
        prepared.position.position_id,
        snapshot_id,
    )

    assert result.outcome is PositionExitDecisionOutcome.CREATED
    assert result.action is StrategyAction.EXIT_LONG
    assert result.reason_codes == (reason, "EXIT_LONG_ALLOWED")
    assert result.position_version == prepared.position.version


def test_exact_six_hour_elapsed_time_creates_exit_long(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.opened_at + timedelta(hours=6)
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price="100",
    )

    result = service(mssql_database.engine, observed_at).decide(
        prepared.position.position_id,
        snapshot_id,
    )

    assert result.action is StrategyAction.EXIT_LONG
    assert result.reason_codes == ("TIME_EXIT_TRIGGERED", "EXIT_LONG_ALLOWED")


def test_untriggered_position_creates_skip(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.updated_at + timedelta(minutes=1)
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price="100",
    )

    result = service(mssql_database.engine, observed_at).decide(
        prepared.position.position_id,
        snapshot_id,
    )

    assert result.action is StrategyAction.SKIP
    assert result.reason_codes == ("EXIT_CONDITIONS_NOT_MET", "POSITION_HOLD")


def test_same_snapshot_is_idempotent_and_preserves_original_identity(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.updated_at + timedelta(minutes=1)
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price="110",
    )
    exit_service = service(mssql_database.engine, observed_at)

    first = exit_service.decide(prepared.position.position_id, snapshot_id)
    second = exit_service.decide(prepared.position.position_id, snapshot_id)
    rows = decisions_for(mssql_database.engine, prepared.position.position_id)

    assert first.outcome is PositionExitDecisionOutcome.CREATED
    assert second.outcome is PositionExitDecisionOutcome.ALREADY_DECIDED
    assert second.decision.decision_id == first.decision.decision_id
    assert second.decision.decided_at == first.decision.decided_at
    assert rows == (first.decision,)


def test_different_snapshot_creates_a_new_decision(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    first_at = prepared.position.updated_at + timedelta(minutes=1)
    second_at = first_at + timedelta(minutes=1)
    first_snapshot = add_snapshot(
        mssql_database.engine,
        observed_at=first_at,
        last_price="100",
    )
    second_snapshot = add_snapshot(
        mssql_database.engine,
        observed_at=second_at,
        last_price="110",
    )

    first = service(mssql_database.engine, first_at).decide(
        prepared.position.position_id,
        first_snapshot,
    )
    second = service(mssql_database.engine, second_at).decide(
        prepared.position.position_id,
        second_snapshot,
    )

    assert first.outcome is second.outcome is PositionExitDecisionOutcome.CREATED
    assert first.decision.decision_id != second.decision.decision_id
    assert len(decisions_for(mssql_database.engine, prepared.position.position_id)) == 2


@pytest.mark.parametrize("case", ["stale", "symbol", "event_version", "strategy"])
def test_invalid_sources_write_no_decision(
    mssql_database: TemporaryMssqlDatabase,
    case: str,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.updated_at + timedelta(minutes=1)
    now = observed_at
    symbol = "AAPL"
    if case == "stale":
        now = observed_at + timedelta(minutes=5, microseconds=1)
    if case == "symbol":
        symbol = "MSFT"
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price="100",
        symbol=symbol,
    )
    if case in {"event_version", "strategy"}:
        values = (
            {"version": prepared.position.version + 1}
            if case == "event_version"
            else {"strategy_id": OBSERVATION_ONLY.strategy_id.value}
        )
        with mssql_database.engine.begin() as connection:
            connection.execute(
                update(paper_positions)
                .where(paper_positions.c.position_id == prepared.position.position_id.value)
                .values(**values)
            )

    with pytest.raises(PositionExitSourceError):
        service(mssql_database.engine, now).decide(
            prepared.position.position_id,
            snapshot_id,
        )

    assert decisions_for(mssql_database.engine, prepared.position.position_id) == ()


def test_success_mutates_only_strategy_decisions(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    prepared = prepare_position(mssql_database.engine)
    observed_at = prepared.position.updated_at + timedelta(minutes=1)
    snapshot_id = add_snapshot(
        mssql_database.engine,
        observed_at=observed_at,
        last_price="110",
    )
    before_counts = source_counts(mssql_database.engine)
    before_position = position_row(
        mssql_database.engine,
        prepared.position.position_id,
    )

    result = service(mssql_database.engine, observed_at).decide(
        prepared.position.position_id,
        snapshot_id,
    )

    assert result.outcome is PositionExitDecisionOutcome.CREATED
    assert source_counts(mssql_database.engine) == before_counts
    assert position_row(mssql_database.engine, prepared.position.position_id) == before_position
