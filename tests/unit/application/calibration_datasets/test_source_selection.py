from typing import cast

from sqlalchemy import Connection
from sqlalchemy.dialects import mssql

from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetProbabilityCalibrationDatasetSourceReader,
)
from auto_trading_v2.adapters.persistence.repositories.calibration_dataset_sources import (
    SqlAlchemyProbabilityCalibrationDatasetSourceReader,
    eligible_calibration_dataset_sources_statement,
)
from auto_trading_v2.domain.calibration_datasets import fixed_dataset_policy_values
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from tests.unit.p4b2a_helpers import DATASET_AS_OF, make_outcomes, make_source


class FakeMappings:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, object]]:
        return self._rows


class FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self._rows)


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls = 0
        self.statement: object | None = None

    def execute(self, statement: object) -> FakeResult:
        self.calls += 1
        self.statement = statement
        return FakeResult(self.rows)


def _row() -> tuple[object, dict[str, object]]:
    source = make_source(make_outcomes((("AAPL", "105"),))[0])
    row = {
        "source_daily_feature_scoring_run_id": source.source_daily_feature_scoring_run_id.value,
        "source_daily_feature_scoring_item_id": source.source_daily_feature_scoring_item_id.value,
        "source_daily_feature_pipeline_run_id": source.source_daily_feature_pipeline_run_id.value,
        "source_daily_feature_pipeline_item_id": source.source_daily_feature_pipeline_item_id.value,
        "feature_snapshot_id": source.feature_snapshot_id.value,
        "source_daily_feature_outcome_id": source.source_daily_feature_outcome_id.value,
        "source_outcome_key": source.source_outcome_key,
        "source_outcome_content_digest": source.source_outcome_content_digest,
        "source_path_revision_digest": source.source_path_revision_digest,
        "symbol": source.symbol.value,
        "mic_code": source.mic_code,
        "horizon_trading_days": source.horizon.value,
        "source_session_date": source.source_session_date.value,
        "terminal_session_date": source.terminal_session_date.value,
        "source_scoring_generated_at": source.source_scoring_generated_at,
        "source_scoring_item_recorded_at": source.source_scoring_item_recorded_at,
        "outcome_latest_input_available_at": source.outcome_latest_input_available_at,
        "outcome_recorded_at": source.outcome_recorded_at,
        "observation_mode": source.observation_mode.value,
        "source_quality_status": source.source_quality_status.value,
        "overall_relative_score": source.overall_relative_score.value,
        "source_rank": source.rank,
        "forward_close_return": source.forward_close_return.value,
        "provider_code": source.provider_code,
        "calendar_code": source.calendar_code,
        "calendar_version": source.calendar_version,
        "outcome_policy_code": source.outcome_policy_code,
        "outcome_policy_version": source.outcome_policy_version,
        "scoring_policy_code": source.scoring_policy_code,
        "scoring_policy_version": source.scoring_policy_version,
        "ranking_policy_code": source.ranking_policy_code,
        "ranking_policy_version": source.ranking_policy_version,
    }
    return source, row


def test_pit_statement_selects_one_latest_revision_after_all_four_cutoffs() -> None:
    statement = eligible_calibration_dataset_sources_statement(TradingDayHorizon(1), DATASET_AS_OF)
    sql = str(
        statement.compile(
            dialect=mssql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    assert "row_number() over" in sql
    assert "partition by trading.daily_feature_outcomes.source_daily_feature_scoring_item_id" in sql
    assert "latest_input_available_at desc" in sql
    assert "recorded_at desc" in sql
    assert "outcome_key desc" in sql
    assert sql.count("<=") >= 4
    assert "scoRed_ready".lower() in sql
    assert "source_quality_status = 'ready'" in sql
    assert "revision_rank = 1" in sql
    assert "order by eligible_calibration_outcome_revisions.source_session_date asc" in sql


def test_reader_maps_all_rows_with_one_query_and_dotnet_reuses_the_same_core_reader() -> None:
    expected, row = _row()
    connection = FakeConnection([row])
    reader = SqlAlchemyProbabilityCalibrationDatasetSourceReader(cast(Connection, connection))

    actual = reader.list_eligible_sources(
        TradingDayHorizon(1), DATASET_AS_OF, *fixed_dataset_policy_values()
    )

    assert actual == (expected,)
    assert connection.calls == 1
    assert issubclass(
        DotNetProbabilityCalibrationDatasetSourceReader,
        SqlAlchemyProbabilityCalibrationDatasetSourceReader,
    )
