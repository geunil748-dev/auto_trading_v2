"""Application-contract builders for repository integration tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from auto_trading_v2.application.contracts.persistence import (
    JSONValue,
    NewCandidate,
    NewFilterEvaluation,
    NewMarketSnapshot,
)
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

PRECISE = Decimal("101.123456789012345678")


def new_snapshot(
    *,
    snapshot_id: MarketSnapshotID | None = None,
    source: str | None = None,
    observed_at: datetime | None = None,
    high_price: Decimal | None = None,
) -> NewMarketSnapshot:
    return NewMarketSnapshot(
        market_snapshot_id=snapshot_id or MarketSnapshotID(uuid4()),
        symbol=Symbol("AAPL"),
        session_date=SessionDate(date(2026, 7, 14)),
        observed_at=observed_at or datetime(2026, 7, 14, 1, 2, 3, 456789, tzinfo=UTC),
        source=source or f"source-{uuid4().hex}",
        open_price=Price(PRECISE),
        high_price=Price(high_price or Decimal("103.123456789012345678")),
        low_price=Price(Decimal("100.123456789012345678")),
        last_price=Price(Decimal("102.123456789012345678")),
        previous_high_price=Price(Decimal("104.123456789012345678")),
        previous_low_price=Price(Decimal("99.123456789012345678")),
        previous_close_price=Price(Decimal("100.623456789012345678")),
        volume=0,
    )


def new_candidate(
    market_snapshot_id: MarketSnapshotID,
    *,
    candidate_id: CandidateID | None = None,
    run_id: RunID | None = None,
    source: str = "RANKING",
    rank: int | None = None,
    selected_at: datetime | None = None,
) -> NewCandidate:
    return NewCandidate(
        candidate_id=candidate_id or CandidateID(uuid4()),
        run_id=run_id or RunID(uuid4()),
        market_snapshot_id=market_snapshot_id,
        candidate_source=source,
        rank=rank,
        source_score=PRECISE,
        selected_at=selected_at or datetime(2026, 7, 14, 1, 3, tzinfo=UTC),
    )


def new_evaluation(
    candidate_id: CandidateID,
    *,
    evaluation_id: FilterEvaluationID | None = None,
    filter_set_id: FilterSetID | None = None,
    version: str = "v1",
    evaluated_at: datetime | None = None,
    details: dict[str, JSONValue] | None = None,
) -> NewFilterEvaluation:
    return NewFilterEvaluation(
        filter_evaluation_id=evaluation_id or FilterEvaluationID(uuid4()),
        candidate_id=candidate_id,
        filter_set_id=filter_set_id or FilterSetID(uuid4()),
        evaluation_version=version,
        passed=True,
        score=PRECISE,
        details=details
        or {
            "decimal": str(PRECISE),
            "nested": {"values": [1, True, None]},
            "한글": "보존",
        },
        evaluated_at=evaluated_at or datetime(2026, 7, 14, 1, 4, tzinfo=UTC),
    )
