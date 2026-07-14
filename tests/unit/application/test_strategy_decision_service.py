from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from auto_trading_v2.application.errors import (
    CandidateNotFoundError,
    InvalidFilterEvaluationError,
    PersistenceError,
    RequiredFilterEvaluationMissingError,
    StrategyDecisionConflictError,
)
from auto_trading_v2.domain.primitives import CandidateID
from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction

from .strategy_decision_fakes import (
    CANDIDATE_ID,
    NOW,
    evaluation_batch,
    service_with,
)


def test_success_reads_sources_and_atomically_stores_four_in_order() -> None:
    service, uow, clock, id_factory = service_with()

    batch = service.decide_all(CANDIDATE_ID)

    assert uow.candidates.get_calls == [CANDIDATE_ID]
    assert uow.filter_evaluations.list_calls == [CANDIDATE_ID]
    assert clock.calls == 1
    assert id_factory.calls == 4
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0
    assert batch.candidate_id == CANDIDATE_ID
    assert tuple(item.strategy_id for item in batch.decisions) == tuple(
        item.strategy_id for item in BUILT_IN_STRATEGIES
    )
    assert tuple(item.filter_evaluation_id for item in batch.decisions) == tuple(
        evaluation.filter_evaluation_id for evaluation in evaluation_batch()
    )
    assert tuple(item.action for item in batch.decisions) == (
        StrategyAction.ENTER_LONG,
        StrategyAction.ENTER_LONG,
        StrategyAction.ENTER_LONG,
        StrategyAction.OBSERVE,
    )
    assert {item.decided_at for item in batch.decisions} == {NOW}
    assert all("candidate:" in item.decision_key for item in batch.decisions)


def test_missing_candidate_stops_before_filter_read_clock_ids_and_writes() -> None:
    service, uow, clock, id_factory = service_with(candidate_present=False)

    with pytest.raises(CandidateNotFoundError):
        service.decide_all(CANDIDATE_ID)

    assert not uow.filter_evaluations.list_calls
    assert not uow.strategy_decisions.add_calls
    assert uow.commit_calls == 0
    assert clock.calls == 0
    assert id_factory.calls == 0


@pytest.mark.parametrize("missing_index", range(4))
def test_each_required_evaluation_is_validated_before_any_write(missing_index: int) -> None:
    evaluations = evaluation_batch()
    evaluations.pop(missing_index)
    service, uow, clock, id_factory = service_with(evaluations)

    with pytest.raises(RequiredFilterEvaluationMissingError):
        service.decide_all(CANDIDATE_ID)

    assert not uow.strategy_decisions.add_calls
    assert uow.commit_calls == 0
    assert clock.calls == 0
    assert id_factory.calls == 0


def test_wrong_version_is_ignored_and_expected_version_is_required() -> None:
    evaluations = evaluation_batch()
    evaluations[0] = replace(evaluations[0], evaluation_version="v2")
    service, uow, clock, _ = service_with(evaluations)

    with pytest.raises(RequiredFilterEvaluationMissingError):
        service.decide_all(CANDIDATE_ID)

    assert not uow.strategy_decisions.add_calls
    assert clock.calls == 0


def test_unrelated_future_version_is_ignored_when_current_exists() -> None:
    evaluations = evaluation_batch()
    evaluations.append(replace(evaluations[0], evaluation_version="v2"))
    service, uow, _, _ = service_with(evaluations)

    batch = service.decide_all(CANDIDATE_ID)

    assert len(batch.decisions) == 4
    assert uow.commit_calls == 1


def test_duplicate_expected_source_is_rejected_before_writes() -> None:
    evaluations = evaluation_batch()
    evaluations.append(
        replace(
            evaluations[0],
            filter_evaluation_id=evaluations[1].filter_evaluation_id,
        )
    )
    service, uow, clock, _ = service_with(evaluations)

    with pytest.raises(InvalidFilterEvaluationError):
        service.decide_all(CANDIDATE_ID)

    assert not uow.strategy_decisions.add_calls
    assert clock.calls == 0


def test_candidate_mismatch_is_rejected_before_writes() -> None:
    evaluations = evaluation_batch()
    evaluations[0] = replace(evaluations[0], candidate_id=CandidateID(uuid4()))
    service, uow, clock, _ = service_with(evaluations)

    with pytest.raises(InvalidFilterEvaluationError) as captured:
        service.decide_all(CANDIDATE_ID)

    assert captured.value.reason == "candidate_mismatch"
    assert not uow.strategy_decisions.add_calls
    assert clock.calls == 0


@pytest.mark.parametrize(
    "invalid",
    [
        {"score": None},
        {"score": Decimal("101")},
        {"passed": False, "details": {"blocking_reason_codes": []}},
        {"details": {"blocking_reason_codes": ["lowercase"]}},
    ],
)
def test_invalid_filter_contract_stops_before_clock_ids_and_writes(
    invalid: dict[str, object],
) -> None:
    evaluations = evaluation_batch()
    evaluations[0] = replace(evaluations[0], **invalid)
    service, uow, clock, id_factory = service_with(evaluations)

    with pytest.raises(InvalidFilterEvaluationError):
        service.decide_all(CANDIDATE_ID)

    assert not uow.strategy_decisions.add_calls
    assert clock.calls == 0
    assert id_factory.calls == 0


def test_duplicate_on_second_insert_rolls_back_complete_batch() -> None:
    service, uow, clock, id_factory = service_with(failure_call=2)

    with pytest.raises(StrategyDecisionConflictError) as captured:
        service.decide_all(CANDIDATE_ID)

    assert captured.value.strategy_name == BUILT_IN_STRATEGIES[1].name
    assert len(uow.strategy_decisions.add_calls) == 2
    assert not uow.strategy_decisions.pending
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert clock.calls == 1
    assert id_factory.calls == 2


def test_other_persistence_error_propagates_and_stops_later_adds() -> None:
    failure = PersistenceError(
        entity="strategy_decision",
        operation="insert",
        reason="operation_failed",
    )
    service, uow, _, _ = service_with(failure_call=2, failure=failure)

    with pytest.raises(PersistenceError) as captured:
        service.decide_all(CANDIDATE_ID)

    assert captured.value is failure
    assert len(uow.strategy_decisions.add_calls) == 2
    assert not uow.strategy_decisions.pending
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_invalid_details_are_not_exposed_by_safe_application_error() -> None:
    sentinel = "SHOULD_NEVER_APPEAR_PR6_a71c2f"
    evaluations = evaluation_batch()
    evaluations[0] = replace(
        evaluations[0],
        passed=False,
        details={"blocking_reason_codes": ["lowercase"], "secret": sentinel},
    )
    service, _, _, _ = service_with(evaluations)

    with pytest.raises(InvalidFilterEvaluationError) as captured:
        service.decide_all(CANDIDATE_ID)

    assert sentinel not in str(captured.value)
    assert sentinel not in repr(captured.value)


def test_service_has_no_filter_recalculation_or_infrastructure_dependencies() -> None:
    source = (
        Path("src/auto_trading_v2/application/services/strategy_decision.py")
        .read_text(encoding="utf-8")
        .lower()
    )

    for forbidden in (
        "filtering.engine",
        "filtering.checks",
        "sqlalchemy",
        "pyodbc",
        "create_engine",
        "load_dotenv",
        "getenv",
        "tradeintent",
        "broker",
    ):
        assert forbidden not in source
