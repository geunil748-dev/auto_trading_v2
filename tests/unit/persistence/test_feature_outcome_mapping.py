from datetime import UTC, date, datetime

import pytest

from auto_trading_v2.adapters.persistence.feature_outcome_mapping import (
    map_daily_feature_outcome,
    new_daily_feature_outcome_values,
)
from auto_trading_v2.adapters.persistence.feature_outcome_observation_mapping import (
    map_outcome_observation_item,
    map_outcome_observation_run,
    new_outcome_observation_item_values,
    new_outcome_observation_run_values,
)
from auto_trading_v2.application.contracts.feature_outcomes import (
    NewDailyFeatureOutcome,
    NewDailyFeatureOutcomeObservationRunWithItems,
)
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineItemOutcome
from tests.unit.application.feature_outcomes.test_service import (
    _command,
    _service,
    _source,
)
from tests.unit.domain.feature_outcomes.helpers import outcome_bar


def _created_result() -> tuple[object, object]:
    scoring, pipeline, snapshots = _source((("AAPL", DailyFeaturePipelineItemOutcome.READY),))
    bar = outcome_bar(
        1,
        close="105",
        high="110",
        low="95",
        session_date=date(2026, 8, 3),
        available_at=datetime(2026, 8, 3, 22, tzinfo=UTC),
    )
    service, factory = _service(scoring, pipeline, snapshots, {"AAPL": (bar,)})
    result = service.observe(_command(scoring))  # type: ignore[arg-type]
    assert result.result is not None
    return next(iter(factory.outcomes.values.values())), result.result


def test_outcome_json_provenance_mapping_round_trip_is_exact() -> None:
    outcome, _ = _created_result()
    values = new_daily_feature_outcome_values(NewDailyFeatureOutcome(outcome))  # type: ignore[arg-type]
    values["recorded_at"] = outcome.recorded_at  # type: ignore[union-attr]

    mapped = map_daily_feature_outcome(values)

    assert mapped == outcome
    assert "open_price" not in str(values["future_bar_provenance"])
    assert "high_price" not in str(values["future_bar_provenance"])
    assert "low_price" not in str(values["future_bar_provenance"])
    assert "close_price" not in str(values["future_bar_provenance"])


def test_observation_run_and_items_mapping_round_trip_is_exact() -> None:
    _, aggregate = _created_result()
    candidate = NewDailyFeatureOutcomeObservationRunWithItems(aggregate)  # type: ignore[arg-type]
    run_values = new_outcome_observation_run_values(candidate)
    run_values["recorded_at"] = aggregate.run.recorded_at  # type: ignore[union-attr]
    mapped_run = map_outcome_observation_run(run_values)
    mapped_items = []
    for item in aggregate.items:  # type: ignore[union-attr]
        values = new_outcome_observation_item_values(item)
        values["recorded_at"] = item.recorded_at
        mapped_items.append(map_outcome_observation_item(values))

    assert mapped_run == aggregate.run  # type: ignore[union-attr]
    assert tuple(mapped_items) == aggregate.items  # type: ignore[union-attr]


def test_mapping_rejects_raw_or_malformed_provenance() -> None:
    outcome, _ = _created_result()
    values = new_daily_feature_outcome_values(NewDailyFeatureOutcome(outcome))  # type: ignore[arg-type]
    values["recorded_at"] = outcome.recorded_at  # type: ignore[union-attr]
    values["future_bar_provenance"] = '{"raw_provider_payload":"forbidden"}'

    with pytest.raises(PersistenceMappingError):
        map_daily_feature_outcome(values)
