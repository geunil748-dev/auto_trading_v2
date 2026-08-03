from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from auto_trading_v2.adapters.persistence.mapping import serialize_json_object
from auto_trading_v2.application.contracts.persistence import NewFilterEvaluation
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.primitives import CandidateID, FilterEvaluationID, FilterSetID


def test_json_serialization_is_unicode_compact_and_stable() -> None:
    evaluation = NewFilterEvaluation(
        filter_evaluation_id=FilterEvaluationID(uuid4()),
        candidate_id=CandidateID(uuid4()),
        filter_set_id=FilterSetID(uuid4()),
        evaluation_version="v1",
        passed=True,
        score=None,
        details={"z": [1, None], "a": "한글"},
        evaluated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert serialize_json_object(evaluation.details) == '{"a":"한글","z":[1,null]}'


def test_serializer_never_coerces_decimal() -> None:
    with pytest.raises(PersistenceMappingError):
        serialize_json_object({"value": Decimal("1")})  # type: ignore[dict-item]
