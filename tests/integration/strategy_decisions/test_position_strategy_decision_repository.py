"""Real MSSQL position strategy-decision repository behavior."""

from dataclasses import replace
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.errors import (
    DuplicateRecordError,
    ForeignKeyViolationError,
)
from auto_trading_v2.domain.primitives import DecisionID, MarketSnapshotID, PositionID
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.persistence.repository_records import new_snapshot
from tests.integration.strategy_decisions.position_helpers import (
    new_position_decision,
    prepare_position_source,
)

pytestmark = pytest.mark.integration


def test_add_get_lookup_and_candidate_mapper_separation(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    source = prepare_position_source(mssql_database.engine)
    decision = new_position_decision(source)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        stored = unit_of_work.strategy_decisions.add_position(decision)
        unit_of_work.commit()

    with factory() as unit_of_work:
        assert unit_of_work.strategy_decisions.get_position(stored.decision_id) == stored
        assert unit_of_work.strategy_decisions.get(stored.decision_id) is None
        assert unit_of_work.strategy_decisions.get_position(source.candidate_decision_id) is None
        assert (
            unit_of_work.strategy_decisions.get_by_position_snapshot_strategy(
                position_id=source.position_id,
                market_snapshot_id=source.market_snapshot_id,
                strategy_id=source.strategy_id,
                strategy_version="v1",
            )
            == stored
        )


@pytest.mark.parametrize("missing", ["position", "snapshot"])
def test_position_repository_translates_foreign_key_violations(
    mssql_database: TemporaryMssqlDatabase,
    missing: str,
) -> None:
    source = prepare_position_source(mssql_database.engine)
    decision = new_position_decision(source)
    if missing == "position":
        decision = replace(decision, position_id=PositionID(uuid4()))
    else:
        decision = replace(decision, market_snapshot_id=MarketSnapshotID(uuid4()))

    with (
        SqlAlchemyUnitOfWorkFactory(mssql_database.engine)() as unit_of_work,
        pytest.raises(ForeignKeyViolationError) as captured,
    ):
        unit_of_work.strategy_decisions.add_position(decision)

    expected = (
        "fk_strategy_decisions_position_id_paper_positions"
        if missing == "position"
        else "fk_strategy_decisions_market_snapshot_id_market_snapshots"
    )
    assert captured.value.constraint == expected


def test_semantic_duplicate_is_rejected_and_failed_batch_rolls_back(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    source = prepare_position_source(mssql_database.engine)
    original = new_position_decision(source)
    duplicate = replace(
        original,
        decision_id=DecisionID(uuid4()),
        decision_key=f"position-duplicate-{uuid4().hex}",
    )
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work, pytest.raises(DuplicateRecordError) as captured:
        unit_of_work.strategy_decisions.add_position(original)
        unit_of_work.strategy_decisions.add_position(duplicate)

    assert captured.value.constraint == "ix_strategy_decisions_position_snapshot_unique"
    with factory() as unit_of_work:
        assert (
            unit_of_work.strategy_decisions.get_by_position_snapshot_strategy(
                position_id=source.position_id,
                market_snapshot_id=source.market_snapshot_id,
                strategy_id=source.strategy_id,
                strategy_version="v1",
            )
            is None
        )


def test_different_snapshot_or_version_has_distinct_semantics(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    source = prepare_position_source(mssql_database.engine)
    other_snapshot = new_snapshot()
    original = new_position_decision(source)
    other_snapshot_decision = new_position_decision(
        source,
        market_snapshot_id=other_snapshot.market_snapshot_id,
    )
    other_version = new_position_decision(source, strategy_version="v2")
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        unit_of_work.market_snapshots.add(other_snapshot)
        stored = (
            unit_of_work.strategy_decisions.add_position(original),
            unit_of_work.strategy_decisions.add_position(other_snapshot_decision),
            unit_of_work.strategy_decisions.add_position(other_version),
        )
        unit_of_work.commit()

    assert len({item.decision_id for item in stored}) == 3


def test_decision_key_remains_globally_unique_for_position_rows(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    source = prepare_position_source(mssql_database.engine)
    original = new_position_decision(source)
    same_key = new_position_decision(
        source,
        decision_key=original.decision_key,
        strategy_version="v2",
    )
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        unit_of_work.strategy_decisions.add_position(original)
        unit_of_work.commit()
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError) as captured:
        unit_of_work.strategy_decisions.add_position(same_key)

    assert captured.value.constraint == "uq_strategy_decisions_decision_key"
