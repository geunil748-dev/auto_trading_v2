"""Builders for strategy-decision MSSQL integration tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import Engine

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidDecisionIDFactory
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.persistence import (
    StoredCandidate,
    StoredFilterEvaluation,
)
from auto_trading_v2.application.contracts.strategy_decisions import (
    NewCandidateStrategyDecision,
    StoredCandidateStrategyDecision,
)
from auto_trading_v2.application.services.strategy_decision import (
    CandidateStrategyDecisionService,
)
from auto_trading_v2.domain.primitives import CandidateID, DecisionID
from auto_trading_v2.domain.strategy_decisions.decision_keys import (
    candidate_strategy_decision_key,
)
from auto_trading_v2.domain.strategy_decisions.engine import (
    DeterministicStrategyDecisionEngine,
)
from auto_trading_v2.domain.strategy_decisions.models import (
    StrategyDefinition,
    StrategyJSONValue,
    StrategySignal,
)
from tests.integration.filtering.helpers import (
    evaluations_for,
    persist_candidate,
)
from tests.integration.filtering.helpers import (
    service as filter_service,
)

DECIDED_AT = datetime(2026, 7, 14, 6, 45, tzinfo=UTC)


def prepare_candidate(engine: Engine, **values: object) -> CandidateID:
    candidate_id = persist_candidate(engine, **values)  # type: ignore[arg-type]
    filter_service(engine).evaluate_all(candidate_id)
    return candidate_id


def strategy_service(engine: Engine) -> CandidateStrategyDecisionService:
    return CandidateStrategyDecisionService(
        SqlAlchemyUnitOfWorkFactory(engine),
        FixedClock(DECIDED_AT),
        UuidDecisionIDFactory(),
    )


def decisions_for(
    engine: Engine, candidate_id: CandidateID
) -> tuple[StoredCandidateStrategyDecision, ...]:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        return tuple(unit_of_work.strategy_decisions.list_by_candidate(candidate_id))


def candidate_for(engine: Engine, candidate_id: CandidateID) -> StoredCandidate:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        stored = unit_of_work.candidates.get(candidate_id)
    assert stored is not None
    return stored


def evaluation_for(
    engine: Engine,
    candidate_id: CandidateID,
    definition: StrategyDefinition,
) -> StoredFilterEvaluation:
    return next(
        evaluation
        for evaluation in evaluations_for(engine, candidate_id)
        if evaluation.filter_set_id == definition.source_filter_set_id
        and evaluation.evaluation_version == definition.source_evaluation_version
    )


def new_decision(
    candidate_id: CandidateID,
    evaluation: StoredFilterEvaluation,
    definition: StrategyDefinition,
    *,
    decision_id: DecisionID | None = None,
    decision_key: str | None = None,
) -> NewCandidateStrategyDecision:
    assert evaluation.score is not None
    signal = StrategySignal(
        filter_set_id=evaluation.filter_set_id,
        evaluation_version=evaluation.evaluation_version,
        passed=evaluation.passed,
        score=evaluation.score,
        details=cast(Mapping[str, StrategyJSONValue], evaluation.details),
    )
    result = DeterministicStrategyDecisionEngine().decide(signal, definition)
    return NewCandidateStrategyDecision(
        decision_id=decision_id or DecisionID(uuid4()),
        decision_key=decision_key
        or candidate_strategy_decision_key(
            candidate_id,
            definition.strategy_id,
            definition.strategy_version,
        ),
        candidate_id=candidate_id,
        filter_evaluation_id=evaluation.filter_evaluation_id,
        strategy_id=definition.strategy_id,
        strategy_version=definition.strategy_version,
        action=result.action,
        reason_codes=result.reason_codes,
        decided_at=DECIDED_AT,
    )


def persist_single_decision(
    engine: Engine,
    decision: NewCandidateStrategyDecision,
) -> StoredCandidateStrategyDecision:
    with SqlAlchemyUnitOfWorkFactory(engine)() as unit_of_work:
        stored = unit_of_work.strategy_decisions.add(decision)
        unit_of_work.commit()
    return stored
