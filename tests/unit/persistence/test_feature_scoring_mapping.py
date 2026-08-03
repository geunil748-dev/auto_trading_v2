from dataclasses import fields

from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetDailyFeatureScoringRunRepository,
)
from auto_trading_v2.adapters.persistence.feature_scoring_mapping import (
    map_scoring_item,
    map_scoring_run,
    new_scoring_item_values,
    new_scoring_run_values,
)
from auto_trading_v2.adapters.persistence.repositories.feature_scoring import (
    SqlAlchemyDailyFeatureScoringRunRepository,
)
from auto_trading_v2.application.contracts.feature_scoring import (
    NewDailyFeatureScoringItem,
    NewDailyFeatureScoringRun,
    RunDailyFeatureScoringCommand,
)
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineItemOutcome
from tests.unit.application.feature_scoring.fakes import service_context


def _new_values() -> tuple[NewDailyFeatureScoringRun, tuple[NewDailyFeatureScoringItem, ...]]:
    context = service_context(
        (
            ("AAPL", DailyFeaturePipelineItemOutcome.READY),
            ("NVDA", DailyFeaturePipelineItemOutcome.DEGRADED),
        )
    )
    source = context.factory.pipeline.aggregate
    assert source is not None
    result = context.service.run(
        RunDailyFeatureScoringCommand(source.run.daily_feature_pipeline_run_id)
    )
    assert result.result is not None
    stored = result.result
    run_names = {field.name for field in fields(NewDailyFeatureScoringRun)}
    item_names = {field.name for field in fields(NewDailyFeatureScoringItem)}
    run = NewDailyFeatureScoringRun(**{name: getattr(stored.run, name) for name in run_names})
    items = tuple(
        NewDailyFeatureScoringItem(**{name: getattr(item, name) for name in item_names})
        for item in stored.items
    )
    return run, items


def test_decimal_values_and_rows_round_trip_without_float() -> None:
    run, items = _new_values()
    run_values = new_scoring_run_values(run)
    item_values = [new_scoring_item_values(item) for item in items]
    recorded_at = items[0].generated_at

    mapped_run = map_scoring_run({**run_values, "recorded_at": recorded_at})
    mapped_items = tuple(
        map_scoring_item({**values, "recorded_at": recorded_at}) for values in item_values
    )

    assert mapped_run == run.stored(recorded_at)
    assert mapped_items == tuple(item.stored(recorded_at) for item in items)
    score_values = {
        value
        for values in item_values
        for key, value in values.items()
        if key.endswith("_score") and value is not None
    }
    assert score_values
    assert all(value.__class__.__name__ == "Decimal" for value in score_values)
    assert mapped_items[1].volume_score is None


def test_dotnet_repository_reuses_exact_canonical_mapping_contract() -> None:
    assert issubclass(
        DotNetDailyFeatureScoringRunRepository,
        SqlAlchemyDailyFeatureScoringRunRepository,
    )
