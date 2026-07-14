"""Canonical parent-row and service builders for filtering integration tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Engine

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.identifiers import UuidFilterEvaluationIDFactory
from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.application.contracts.persistence import (
    NewCandidate,
    NewFilterEvaluation,
    NewMarketSnapshot,
    StoredFilterEvaluation,
)
from auto_trading_v2.application.services.filter_evaluation import (
    CandidateFilterEvaluationService,
)
from auto_trading_v2.domain.filtering.catalog import BALANCED
from auto_trading_v2.domain.primitives import (
    CandidateID,
    FilterEvaluationID,
    MarketSnapshotID,
    Price,
    RunID,
    SessionDate,
    Symbol,
)

EVALUATED_AT = datetime(2026, 7, 14, 6, 30, tzinfo=UTC)


def persist_candidate(
    engine: Engine,
    *,
    open_price: str,
    last_price: str,
    previous_high: str,
    previous_low: str,
    previous_close: str | None,
    volume: int | None = 100,
    current_high: str | None = None,
    current_low: str | None = None,
) -> CandidateID:
    snapshot_id = MarketSnapshotID(uuid4())
    candidate_id = CandidateID(uuid4())
    open_value = Decimal(open_price)
    last_value = Decimal(last_price)
    high_value = Decimal(current_high) if current_high else max(open_value, last_value) + 1
    low_value = Decimal(current_low) if current_low else min(open_value, last_value) - 1
    snapshot = NewMarketSnapshot(
        market_snapshot_id=snapshot_id,
        symbol=Symbol("AAPL"),
        session_date=SessionDate(date(2026, 7, 14)),
        observed_at=EVALUATED_AT,
        source=f"filter-{uuid4().hex}",
        open_price=Price(open_value),
        high_price=Price(high_value),
        low_price=Price(low_value),
        last_price=Price(last_value),
        previous_high_price=Price(Decimal(previous_high)),
        previous_low_price=Price(Decimal(previous_low)),
        previous_close_price=(None if previous_close is None else Price(Decimal(previous_close))),
        volume=volume,
    )
    candidate = NewCandidate(
        candidate_id=candidate_id,
        run_id=RunID(uuid4()),
        market_snapshot_id=snapshot_id,
        candidate_source="FILTER_TEST",
        rank=None,
        source_score=None,
        selected_at=EVALUATED_AT,
    )
    factory = SqlAlchemyUnitOfWorkFactory(engine)
    with factory() as unit_of_work:
        unit_of_work.market_snapshots.add(snapshot)
        unit_of_work.candidates.add(candidate)
        unit_of_work.commit()
    return candidate_id


def service(engine: Engine) -> CandidateFilterEvaluationService:
    return CandidateFilterEvaluationService(
        SqlAlchemyUnitOfWorkFactory(engine),
        FixedClock(EVALUATED_AT),
        UuidFilterEvaluationIDFactory(),
    )


def evaluations_for(
    engine: Engine, candidate_id: CandidateID
) -> tuple[StoredFilterEvaluation, ...]:
    factory = SqlAlchemyUnitOfWorkFactory(engine)
    with factory() as unit_of_work:
        return tuple(unit_of_work.filter_evaluations.list_by_candidate(candidate_id))


def persist_balanced_evaluation(
    engine: Engine, candidate_id: CandidateID
) -> StoredFilterEvaluation:
    existing = NewFilterEvaluation(
        filter_evaluation_id=FilterEvaluationID(uuid4()),
        candidate_id=candidate_id,
        filter_set_id=BALANCED.filter_set_id,
        evaluation_version=BALANCED.evaluation_version,
        passed=True,
        score=Decimal("70"),
        details={"seed": "existing"},
        evaluated_at=EVALUATED_AT,
    )
    factory = SqlAlchemyUnitOfWorkFactory(engine)
    with factory() as unit_of_work:
        stored = unit_of_work.filter_evaluations.add(existing)
        unit_of_work.commit()
    return stored
