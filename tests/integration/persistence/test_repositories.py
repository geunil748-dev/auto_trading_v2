"""Real MSSQL repository round-trip and constraint tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyCandidateRepository,
    SqlAlchemyFilterEvaluationRepository,
    SqlAlchemyMarketSnapshotRepository,
)
from auto_trading_v2.adapters.persistence.tables import (
    candidates,
    filter_evaluations,
    market_snapshots,
)
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.persistence import NewFilterEvaluation
from auto_trading_v2.application.errors import (
    CheckConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    FilterEvaluationID,
    FilterSetID,
    MarketSnapshotID,
    RunID,
)
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.persistence.repository_records import (
    PRECISE,
    new_candidate,
    new_evaluation,
    new_snapshot,
)

pytestmark = pytest.mark.integration


def test_all_repositories_round_trip_and_share_one_transaction(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()
    candidate = new_candidate(snapshot.market_snapshot_id, rank=None)
    evaluation = new_evaluation(candidate.candidate_id)

    with factory() as uow:
        stored_snapshot = uow.market_snapshots.add(snapshot)
        assert uow.market_snapshots.get(snapshot.market_snapshot_id) == stored_snapshot
        assert (
            uow.market_snapshots.get_by_observation(
                source=snapshot.source,
                symbol=snapshot.symbol,
                observed_at=snapshot.observed_at,
            )
            == stored_snapshot
        )
        stored_candidate = uow.candidates.add(candidate)
        assert uow.candidates.get(candidate.candidate_id) == stored_candidate
        stored_evaluation = uow.filter_evaluations.add(evaluation)
        assert uow.filter_evaluations.get(evaluation.filter_evaluation_id) == stored_evaluation
        uow.commit()

    assert stored_snapshot.open_price.value == PRECISE
    assert stored_snapshot.observed_at == snapshot.observed_at
    assert stored_snapshot.recorded_at.tzinfo is UTC
    assert stored_candidate.rank is None
    assert stored_candidate.source_score == PRECISE
    assert stored_evaluation.score == PRECISE
    assert stored_evaluation.details["한글"] == "보존"
    assert stored_evaluation.details["decimal"] == str(PRECISE)

    with factory() as reader:
        assert reader.market_snapshots.get(snapshot.market_snapshot_id) is not None
        assert reader.candidates.get(candidate.candidate_id) is not None
        assert reader.filter_evaluations.get(evaluation.filter_evaluation_id) is not None


def test_lists_are_deterministically_ordered(mssql_database: TemporaryMssqlDatabase) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()
    run_id = RunID(uuid4())
    base = datetime(2026, 7, 14, 2, tzinfo=UTC)
    later = new_candidate(
        snapshot.market_snapshot_id, run_id=run_id, source="LATER", selected_at=base + timedelta(1)
    )
    earlier = new_candidate(
        snapshot.market_snapshot_id, run_id=run_id, source="EARLIER", selected_at=base
    )
    filter_set_id = FilterSetID(uuid4())
    later_eval = new_evaluation(
        earlier.candidate_id,
        filter_set_id=filter_set_id,
        version="later",
        evaluated_at=base + timedelta(2),
    )
    earlier_eval = new_evaluation(
        earlier.candidate_id,
        filter_set_id=filter_set_id,
        version="earlier",
        evaluated_at=base + timedelta(1),
    )

    with factory() as uow:
        uow.market_snapshots.add(snapshot)
        uow.candidates.add(later)
        uow.candidates.add(earlier)
        uow.filter_evaluations.add(later_eval)
        uow.filter_evaluations.add(earlier_eval)
        assert [item.candidate_id for item in uow.candidates.list_by_run(run_id)] == [
            earlier.candidate_id,
            later.candidate_id,
        ]
        assert [
            item.filter_evaluation_id
            for item in uow.filter_evaluations.list_by_candidate(earlier.candidate_id)
        ] == [earlier_eval.filter_evaluation_id, later_eval.filter_evaluation_id]
        uow.commit()


def test_direct_repositories_never_commit(mssql_database: TemporaryMssqlDatabase) -> None:
    snapshot = new_snapshot()
    candidate = new_candidate(snapshot.market_snapshot_id)
    evaluation = new_evaluation(candidate.candidate_id)

    with mssql_database.engine.connect() as connection:
        SqlAlchemyMarketSnapshotRepository(connection).add(snapshot)
        SqlAlchemyCandidateRepository(connection).add(candidate)
        SqlAlchemyFilterEvaluationRepository(connection).add(evaluation)

    with mssql_database.engine.connect() as connection:
        assert (
            connection.execute(
                select(market_snapshots.c.market_snapshot_id).where(
                    market_snapshots.c.market_snapshot_id == snapshot.market_snapshot_id.value
                )
            ).one_or_none()
            is None
        )
        assert (
            connection.execute(
                select(candidates.c.candidate_id).where(
                    candidates.c.candidate_id == candidate.candidate_id.value
                )
            ).one_or_none()
            is None
        )
        assert (
            connection.execute(
                select(filter_evaluations.c.filter_evaluation_id).where(
                    filter_evaluations.c.filter_evaluation_id
                    == evaluation.filter_evaluation_id.value
                )
            ).one_or_none()
            is None
        )


@pytest.mark.parametrize("entity", ["snapshot", "candidate", "evaluation"])
def test_duplicate_natural_keys_are_translated(
    mssql_database: TemporaryMssqlDatabase,
    entity: str,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    snapshot = new_snapshot()
    candidate = new_candidate(snapshot.market_snapshot_id)
    evaluation = new_evaluation(candidate.candidate_id)
    with factory() as setup:
        setup.market_snapshots.add(snapshot)
        if entity != "snapshot":
            setup.candidates.add(candidate)
        if entity == "evaluation":
            setup.filter_evaluations.add(evaluation)
        setup.commit()

    with pytest.raises(DuplicateRecordError) as caught, factory() as uow:
        if entity == "snapshot":
            uow.market_snapshots.add(
                replace(snapshot, market_snapshot_id=MarketSnapshotID(uuid4()))
            )
        elif entity == "candidate":
            uow.candidates.add(replace(candidate, candidate_id=CandidateID(uuid4())))
        else:
            uow.filter_evaluations.add(
                replace(evaluation, filter_evaluation_id=FilterEvaluationID(uuid4()))
            )

    assert "INSERT" not in str(caught.value)
    assert "parameter" not in str(caught.value)


def test_fk_and_check_violations_are_translated(mssql_database: TemporaryMssqlDatabase) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    invalid_candidate = new_candidate(MarketSnapshotID(uuid4()))
    with pytest.raises(ForeignKeyViolationError), factory() as uow:
        uow.candidates.add(invalid_candidate)

    invalid_evaluation = new_evaluation(CandidateID(uuid4()))
    with pytest.raises(ForeignKeyViolationError), factory() as uow:
        uow.filter_evaluations.add(invalid_evaluation)

    invalid_snapshot = new_snapshot(high_price=Decimal("100.500000000000000000"))
    with pytest.raises(CheckConstraintViolationError), factory() as uow:
        uow.market_snapshots.add(invalid_snapshot)


def test_filter_json_contract_rejects_decimal_before_sql(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    del mssql_database
    with pytest.raises(ValidationError):
        NewFilterEvaluation(
            filter_evaluation_id=FilterEvaluationID(uuid4()),
            candidate_id=CandidateID(uuid4()),
            filter_set_id=FilterSetID(uuid4()),
            evaluation_version="v1",
            passed=True,
            score=None,
            details={"decimal": PRECISE},  # type: ignore[dict-item]
            evaluated_at=datetime(2026, 7, 14, tzinfo=UTC),
        )
