import json
from typing import cast

import pytest
from sqlalchemy import Connection
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetProbabilityCalibrationDatasetRepository,
)
from auto_trading_v2.adapters.persistence.repositories.calibration_dataset_readiness import (
    map_training_readiness_lineage_record,
    training_readiness_lineage_statement,
)
from auto_trading_v2.adapters.persistence.repositories.calibration_datasets import (
    SqlAlchemyProbabilityCalibrationDatasetRepository,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.feature_building import PRICE_FEATURE_NAMES
from tests.unit.training_readiness_helpers import aggregate


class FakeMappings:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def all(self) -> list[dict[str, object]]:
        return self.rows


class FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self.rows)


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls = 0
        self.statement: object | None = None

    def execute(self, statement: object) -> FakeResult:
        self.calls += 1
        self.statement = statement
        return FakeResult(self.rows)


def _row() -> dict[str, object]:
    value = aggregate()
    item = value.items[0]
    identity = value.dataset.identity
    return {
        "daily_feature_scoring_item_id": item.source_daily_feature_scoring_item_id.value,
        "symbol": item.symbol.value,
        "mic_code": item.mic_code,
        "source_session_date": item.source_session_date.value,
        "provider_code": identity.provider_code,
        "calendar_code": identity.calendar_code.value,
        "calendar_version": identity.calendar_version.value,
        "scoring_policy_code": identity.scoring_policy_code.value,
        "scoring_policy_version": identity.scoring_policy_version.value,
        "ranking_policy_code": identity.ranking_policy_code.value,
        "ranking_policy_version": identity.ranking_policy_version.value,
        "scoring_outcome": "SCORED_READY",
        "source_quality_status": "READY",
        "pipeline_outcome": "READY",
        "feature_set_code": "US_EQUITY_DAILY_TECHNICAL",
        "feature_set_version": "v1",
        "feature_quality_status": "READY",
        "quality_reason_codes": "[]",
        "feature_values": json.dumps(
            {
                **{name: str(index + 1) for index, name in enumerate(PRICE_FEATURE_NAMES)},
                "adjustment_basis": "SPLIT_ADJUSTED",
                "completed_bar_count": 21,
            }
        ),
        "overall_relative_score": item.overall_relative_score.value,
        "source_rank": item.source_rank,
        "has_any_outcome": 1,
        "has_as_of_outcome": 1,
        "has_provider_outcome": 1,
        "has_calendar_outcome": 1,
        "has_policy_outcome": 1,
        "has_any_label": 1,
        "has_matching_label": 1,
    }


def test_statement_is_select_only_point_in_time_and_provider_neutral() -> None:
    dataset = aggregate().dataset
    statement = training_readiness_lineage_statement(dataset)
    sql = str(
        statement.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True})
    ).casefold()

    assert sql.lstrip().startswith("select")
    assert "daily_feature_scoring_items" in sql
    assert "daily_feature_outcomes" in sql
    assert "daily_feature_outcome_labels" in sql
    assert sql.count("exists (select 1") >= 7
    assert sql.count("<=") >= 4
    assert " insert " not in sql
    assert " update " not in sql
    assert " delete " not in sql
    assert "apikey" not in sql
    assert issubclass(
        DotNetProbabilityCalibrationDatasetRepository,
        SqlAlchemyProbabilityCalibrationDatasetRepository,
    )


def test_repository_maps_all_rows_with_one_read_and_rejects_raw_bad_json() -> None:
    dataset = aggregate().dataset
    row = _row()
    expected = map_training_readiness_lineage_record(row)
    connection = FakeConnection([row])
    repository = SqlAlchemyProbabilityCalibrationDatasetRepository(cast(Connection, connection))

    actual = repository.list_training_readiness_lineage(dataset)

    assert actual == (expected,)
    assert connection.calls == 1
    bad = dict(row, quality_reason_codes='{"raw":"provider body"}')
    with pytest.raises(PersistenceMappingError) as captured:
        map_training_readiness_lineage_record(bad)
    assert "provider body" not in str(captured.value)
