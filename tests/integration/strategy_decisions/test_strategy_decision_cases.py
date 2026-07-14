"""Real MSSQL action and reason-code matrix over the four PR5 cases."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction
from tests.integration.filtering.helpers import evaluations_for
from tests.integration.persistence.conftest import TemporaryMssqlDatabase
from tests.integration.strategy_decisions.helpers import (
    decisions_for,
    prepare_candidate,
    strategy_service,
)

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    values: dict[str, object]
    actions: tuple[StrategyAction, ...]
    entry_reasons: tuple[tuple[str, ...], ...]


ENTER = ("FILTER_SET_PASSED", "ENTRY_ALLOWED")
CASES = (
    Case(
        "all-pass",
        {
            "open_price": "22.66",
            "last_price": "25",
            "previous_high": "20",
            "previous_low": "10",
            "previous_close": "22",
        },
        (
            StrategyAction.ENTER_LONG,
            StrategyAction.ENTER_LONG,
            StrategyAction.ENTER_LONG,
            StrategyAction.OBSERVE,
        ),
        (ENTER, ENTER, ENTER),
    ),
    Case(
        "breakout-fails",
        {
            "open_price": "22.66",
            "last_price": "24",
            "previous_high": "20",
            "previous_low": "10",
            "previous_close": "22",
        },
        (
            StrategyAction.SKIP,
            StrategyAction.ENTER_LONG,
            StrategyAction.ENTER_LONG,
            StrategyAction.OBSERVE,
        ),
        (
            (
                "FILTER_SET_FAILED",
                "HARD_CHECK_FAILED",
                "SCORE_BELOW_MINIMUM",
                "ENTRY_BLOCKED",
            ),
            ENTER,
            ENTER,
        ),
    ),
    Case(
        "previous-close-missing",
        {
            "open_price": "22.66",
            "last_price": "25",
            "previous_high": "20",
            "previous_low": "10",
            "previous_close": None,
        },
        (
            StrategyAction.SKIP,
            StrategyAction.SKIP,
            StrategyAction.ENTER_LONG,
            StrategyAction.OBSERVE,
        ),
        (
            (
                "FILTER_SET_FAILED",
                "HARD_CHECK_NOT_EVALUABLE",
                "SCORE_BELOW_MINIMUM",
                "ENTRY_BLOCKED",
            ),
            (
                "FILTER_SET_FAILED",
                "HARD_CHECK_NOT_EVALUABLE",
                "SCORE_BELOW_MINIMUM",
                "ENTRY_BLOCKED",
            ),
            ENTER,
        ),
    ),
    Case(
        "price-range-fails",
        {
            "open_price": "309",
            "last_price": "301",
            "previous_high": "200",
            "previous_low": "100",
            "previous_close": "300",
            "current_high": "310",
            "current_low": "250",
        },
        (
            StrategyAction.SKIP,
            StrategyAction.SKIP,
            StrategyAction.ENTER_LONG,
            StrategyAction.OBSERVE,
        ),
        (
            (
                "FILTER_SET_FAILED",
                "HARD_CHECK_FAILED",
                "SCORE_BELOW_MINIMUM",
                "ENTRY_BLOCKED",
            ),
            ("FILTER_SET_FAILED", "HARD_CHECK_FAILED", "ENTRY_BLOCKED"),
            ENTER,
        ),
    ),
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_case_actions_links_and_reasons_are_exact(
    mssql_database: TemporaryMssqlDatabase,
    case: Case,
) -> None:
    candidate_id = prepare_candidate(mssql_database.engine, **case.values)

    batch = strategy_service(mssql_database.engine).decide_all(candidate_id)

    assert tuple(item.action for item in batch.decisions) == case.actions
    assert tuple(item.reason_codes for item in batch.decisions[:3]) == case.entry_reasons
    assert batch.decisions[3].reason_codes == ("OBSERVATION_ONLY",)
    assert tuple(item.strategy_id for item in batch.decisions) == tuple(
        definition.strategy_id for definition in BUILT_IN_STRATEGIES
    )
    evaluations = evaluations_for(mssql_database.engine, candidate_id)
    expected_links = {
        definition.strategy_id: next(
            evaluation.filter_evaluation_id
            for evaluation in evaluations
            if evaluation.filter_set_id == definition.source_filter_set_id
            and evaluation.evaluation_version == definition.source_evaluation_version
        )
        for definition in BUILT_IN_STRATEGIES
    }
    assert {
        item.strategy_id: item.filter_evaluation_id for item in batch.decisions
    } == expected_links
    assert len(decisions_for(mssql_database.engine, candidate_id)) == 4
    assert all(item.action is not StrategyAction.ENTER_LONG for item in batch.decisions[3:])
