from datetime import UTC, datetime
from inspect import getmembers, isfunction
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.repositories.strategy_decisions import (
    SqlAlchemyStrategyDecisionRepository,
    deserialize_reason_codes,
    map_strategy_decision,
    serialize_reason_codes,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.ports.strategy_decisions import StrategyDecisionRepository
from auto_trading_v2.domain.strategy_decisions.models import StrategyAction


def row() -> dict[str, object]:
    return {
        "decision_id": uuid4(),
        "decision_key": "candidate:key|strategy:key|version:v1",
        "candidate_id": uuid4(),
        "position_id": None,
        "filter_evaluation_id": uuid4(),
        "strategy_id": uuid4(),
        "strategy_version": "v1",
        "action": "ENTER_LONG",
        "reason_codes": '["FILTER_SET_PASSED","ENTRY_ALLOWED"]',
        "decided_at": datetime(2026, 7, 14, 6, tzinfo=UTC),
        "recorded_at": datetime(2026, 7, 14, 6, 1, tzinfo=UTC),
    }


def test_repository_protocol_has_only_required_read_and_add_methods() -> None:
    methods = {
        name
        for name, value in getmembers(StrategyDecisionRepository, isfunction)
        if not name.startswith("_")
    }

    assert methods == {"add", "get", "get_by_candidate_strategy", "list_by_candidate"}
    assert not {"update", "delete", "upsert"}.intersection(methods)


def test_reason_codes_json_is_compact_stable_and_round_trips() -> None:
    codes = ("FILTER_SET_FAILED", "HARD_CHECK_FAILED", "ENTRY_BLOCKED")

    serialized = serialize_reason_codes(codes)

    assert serialized == '["FILTER_SET_FAILED","HARD_CHECK_FAILED","ENTRY_BLOCKED"]'
    assert deserialize_reason_codes(serialized) == codes


@pytest.mark.parametrize("raw", ["{}", "[]", '["lowercase"]', '["A","A"]', "[invalid"])
def test_invalid_reason_json_is_rejected_without_raw_payload(raw: str) -> None:
    with pytest.raises(PersistenceMappingError) as captured:
        deserialize_reason_codes(raw)

    assert raw not in str(captured.value)
    assert raw not in repr(captured.value)


def test_mapping_returns_candidate_contract_and_rejects_position_row() -> None:
    mapped = map_strategy_decision(row())

    assert mapped.action is StrategyAction.ENTER_LONG
    assert mapped.reason_codes == ("FILTER_SET_PASSED", "ENTRY_ALLOWED")
    invalid = row()
    invalid["position_id"] = uuid4()
    invalid["candidate_id"] = None
    invalid["filter_evaluation_id"] = None
    with pytest.raises(PersistenceMappingError):
        map_strategy_decision(invalid)


def test_repository_owns_no_transaction_or_mutation_methods() -> None:
    names = set(dir(SqlAlchemyStrategyDecisionRepository))

    assert not {"commit", "rollback", "begin", "update", "delete", "upsert"}.intersection(names)
