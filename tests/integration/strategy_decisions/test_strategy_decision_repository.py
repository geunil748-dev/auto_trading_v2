"""Real MSSQL candidate strategy-decision repository and constraints."""

from dataclasses import replace
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.errors import DuplicateRecordError, ForeignKeyViolationError
from auto_trading_v2.domain.primitives import (
    CandidateID,
    DecisionID,
    FilterEvaluationID,
    StrategyID,
)
from auto_trading_v2.domain.strategy_decisions.catalog import BALANCED_ENTRY, STRICT_ENTRY
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import (
    evaluation_for,
    new_decision,
    prepare_candidate,
)

pytestmark = pytest.mark.integration


def _candidate(mssql_database: TemporaryMssqlDatabase) -> CandidateID:
    return prepare_candidate(
        mssql_database.engine,
        open_price="22.66",
        last_price="25",
        previous_high="20",
        previous_low="10",
        previous_close="22",
    )


def test_repository_add_get_lookup_and_list_round_trip(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = _candidate(mssql_database)
    evaluation = evaluation_for(mssql_database.engine, candidate_id, STRICT_ENTRY)
    decision = new_decision(candidate_id, evaluation, STRICT_ENTRY)
    balanced = new_decision(
        candidate_id,
        evaluation_for(mssql_database.engine, candidate_id, BALANCED_ENTRY),
        BALANCED_ENTRY,
    )
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)

    with factory() as unit_of_work:
        stored = unit_of_work.strategy_decisions.add(decision)
        stored_balanced = unit_of_work.strategy_decisions.add(balanced)
        unit_of_work.commit()
    with factory() as unit_of_work:
        assert unit_of_work.strategy_decisions.get(stored.decision_id) == stored
        assert (
            unit_of_work.strategy_decisions.get_by_candidate_strategy(
                candidate_id=candidate_id,
                strategy_id=STRICT_ENTRY.strategy_id,
                strategy_version="v1",
            )
            == stored
        )
        listed = unit_of_work.strategy_decisions.list_by_candidate(candidate_id)
        assert {item.decision_id for item in listed} == {
            stored.decision_id,
            stored_balanced.decision_id,
        }
        assert unit_of_work.strategy_decisions.list_by_candidate(candidate_id) == listed


@pytest.mark.parametrize("missing", ["candidate", "evaluation"])
def test_repository_translates_foreign_key_violations(
    mssql_database: TemporaryMssqlDatabase,
    missing: str,
) -> None:
    candidate_id = _candidate(mssql_database)
    evaluation = evaluation_for(mssql_database.engine, candidate_id, STRICT_ENTRY)
    decision = new_decision(candidate_id, evaluation, STRICT_ENTRY)
    if missing == "candidate":
        decision = replace(decision, candidate_id=CandidateID(uuid4()))
    else:
        decision = replace(
            decision,
            filter_evaluation_id=FilterEvaluationID(uuid4()),
        )

    with (
        SqlAlchemyUnitOfWorkFactory(mssql_database.engine)() as unit_of_work,
        pytest.raises(ForeignKeyViolationError),
    ):
        unit_of_work.strategy_decisions.add(decision)


def test_duplicate_key_and_candidate_strategy_version_are_rejected(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    candidate_id = _candidate(mssql_database)
    strict_evaluation = evaluation_for(mssql_database.engine, candidate_id, STRICT_ENTRY)
    balanced_evaluation = evaluation_for(mssql_database.engine, candidate_id, BALANCED_ENTRY)
    original = new_decision(candidate_id, strict_evaluation, STRICT_ENTRY)
    factory = SqlAlchemyUnitOfWorkFactory(mssql_database.engine)
    with factory() as unit_of_work:
        unit_of_work.strategy_decisions.add(original)
        unit_of_work.commit()

    same_key = replace(
        new_decision(candidate_id, balanced_evaluation, BALANCED_ENTRY),
        strategy_id=StrategyID(uuid4()),
        decision_key=original.decision_key,
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.strategy_decisions.add(same_key)

    same_semantics = replace(
        original,
        decision_id=DecisionID(uuid4()),
        decision_key=f"candidate:{candidate_id.serialize()}|strategy:alternate|version:v1",
    )
    with factory() as unit_of_work, pytest.raises(DuplicateRecordError):
        unit_of_work.strategy_decisions.add(same_semantics)
