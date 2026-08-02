from decimal import Decimal

import pytest

from auto_trading_v2.adapters.persistence.calibration_dataset_item_mapping import (
    map_probability_calibration_dataset_item,
    new_probability_calibration_dataset_item_values,
)
from auto_trading_v2.adapters.persistence.calibration_dataset_mapping import (
    map_probability_calibration_dataset,
    new_probability_calibration_dataset_values,
)
from auto_trading_v2.adapters.persistence.outcome_label_mapping import (
    map_daily_feature_outcome_label,
    new_daily_feature_outcome_label_values,
)
from auto_trading_v2.application.contracts.calibration_datasets import (
    NewProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.application.contracts.outcome_labels import NewDailyFeatureOutcomeLabel
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.application.services.probability_calibration_dataset_builder import (
    build_calibration_dataset,
    validate_and_order_sources,
)
from tests.unit.application.p4b2a_fakes import DatasetIDs, ItemIDs
from tests.unit.p4b2a_helpers import (
    GENERATED_AT,
    dataset_identity,
    make_label,
    make_outcomes,
    make_source,
)


def _aggregate() -> object:
    outcomes = make_outcomes((("MSFT", "95"), ("AAPL", "105")))
    sources = validate_and_order_sources(
        (make_source(outcomes[0], rank=2), make_source(outcomes[1], rank=1)),
        dataset_identity(),
    )
    labels_by_outcome = {
        outcome.daily_feature_outcome_id: make_label(outcome, identifier=94_000 + index)
        for index, outcome in enumerate(outcomes, 1)
    }
    labels = tuple(labels_by_outcome[source.source_daily_feature_outcome_id] for source in sources)
    return build_calibration_dataset(
        dataset_identity(), sources, labels, GENERATED_AT, DatasetIDs(), ItemIDs()
    )


def test_label_mapping_round_trip_is_exact_and_has_no_raw_return_field() -> None:
    label = make_label(make_outcomes((("AAPL", "105"),))[0])
    values = new_daily_feature_outcome_label_values(NewDailyFeatureOutcomeLabel(label))
    values["recorded_at"] = label.recorded_at

    assert map_daily_feature_outcome_label(values) == label
    assert "forward_close_return" not in values
    assert "probability" not in values


def test_dataset_and_decimal_item_mapping_round_trip_is_exact() -> None:
    aggregate = _aggregate()
    candidate = NewProbabilityCalibrationDatasetWithItems(aggregate)  # type: ignore[arg-type]
    dataset_values = new_probability_calibration_dataset_values(candidate)
    dataset_values["recorded_at"] = aggregate.dataset.recorded_at  # type: ignore[union-attr]
    mapped_dataset = map_probability_calibration_dataset(dataset_values)
    mapped_items = []
    for item in aggregate.items:  # type: ignore[union-attr]
        values = new_probability_calibration_dataset_item_values(item)
        assert isinstance(values["overall_relative_score"], Decimal)
        values["recorded_at"] = item.recorded_at
        mapped_items.append(map_probability_calibration_dataset_item(values))

    assert mapped_dataset == aggregate.dataset  # type: ignore[union-attr]
    assert tuple(mapped_items) == aggregate.items  # type: ignore[union-attr]


def test_dataset_item_mapping_rejects_float_score_and_payload_like_text() -> None:
    aggregate = _aggregate()
    item = aggregate.items[0]  # type: ignore[union-attr]
    values = new_probability_calibration_dataset_item_values(item)
    values["recorded_at"] = item.recorded_at
    values["overall_relative_score"] = 75.5

    with pytest.raises(PersistenceMappingError):
        map_probability_calibration_dataset_item(values)

    values["overall_relative_score"] = item.overall_relative_score.value
    values["source_outcome_content_digest"] = '{"raw_provider_payload":"forbidden"}'
    with pytest.raises(PersistenceMappingError):
        map_probability_calibration_dataset_item(values)
