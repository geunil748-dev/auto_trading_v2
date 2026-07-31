import json

import pytest

from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetDailyFeaturePipelineRunRepository,
    DotNetUniverseSnapshotRepository,
)
from auto_trading_v2.adapters.persistence.feature_pipeline_mapping import (
    map_pipeline_item,
    map_pipeline_run,
    new_pipeline_item_values,
    new_pipeline_run_values,
)
from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyDailyFeaturePipelineRunRepository,
    SqlAlchemyUniverseSnapshotRepository,
)
from auto_trading_v2.adapters.persistence.universe_mapping import (
    map_universe_snapshot,
    new_universe_snapshot_values,
    serialize_universe_members,
)
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineItem,
    NewDailyFeaturePipelineRun,
)
from auto_trading_v2.application.contracts.universes import NewUniverseSnapshot
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineRunWithItems
from tests.unit.application.feature_pipeline.fakes import command, service, universe


def test_universe_json_and_row_mapping_are_canonical_and_exact() -> None:
    snapshot = universe("NVDA", "AAPL", "MSFT")
    new = NewUniverseSnapshot(
        snapshot.universe_snapshot_id,
        snapshot.universe_key,
        snapshot.content_digest,
        snapshot.definition,
        snapshot.generated_at,
    )
    values = new_universe_snapshot_values(new)
    values["recorded_at"] = snapshot.recorded_at

    encoded = serialize_universe_members(snapshot.definition)
    assert encoded == json.dumps(
        [
            {"mic_code": "XNGS", "symbol": "AAPL"},
            {"mic_code": "XNGS", "symbol": "MSFT"},
            {"mic_code": "XNGS", "symbol": "NVDA"},
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    assert map_universe_snapshot(values) == snapshot


def test_run_and_item_mapping_round_trip_preserves_order_and_nullable_shapes() -> None:
    snapshot = universe("AAPL", "MSFT")
    context = service(snapshot)
    context.features.scripts["MSFT"] = None
    aggregate = context.service.run(command(snapshot)).result
    run = aggregate.run
    new_run = NewDailyFeaturePipelineRun(
        run.daily_feature_pipeline_run_id,
        run.run_key,
        run.content_digest,
        run.identity,
        run.status,
        run.total_count,
        run.ready_count,
        run.degraded_count,
        run.data_insufficient_count,
        run.no_data_count,
        run.provider_error_count,
        run.calendar_error_count,
        run.not_attempted_count,
        run.estimated_credit_count,
        run.consumed_credit_count,
        run.started_at,
        run.finished_at,
    )
    run_values = new_pipeline_run_values(new_run)
    run_values["recorded_at"] = run.recorded_at
    mapped_items = []
    for item in aggregate.items:
        new_item = NewDailyFeaturePipelineItem(
            item.daily_feature_pipeline_item_id,
            item.daily_feature_pipeline_run_id,
            item.ordinal,
            item.symbol,
            item.mic_code,
            item.completed_session_date,
            item.outcome,
            item.daily_bar_created_count,
            item.daily_bar_existing_count,
            item.feature_snapshot_id,
            item.feature_quality_status,
            item.safe_reason_code,
            item.provider_request_count,
            item.provider_credit_count,
            item.started_at,
            item.finished_at,
        )
        item_values = new_pipeline_item_values(new_item)
        item_values["recorded_at"] = item.recorded_at
        mapped_items.append(map_pipeline_item(item_values))

    mapped = DailyFeaturePipelineRunWithItems(
        map_pipeline_run(run_values),
        tuple(mapped_items),
    )
    assert mapped == aggregate
    assert mapped.items[0].feature_snapshot_id is not None
    assert mapped.items[1].feature_snapshot_id is None


def test_mapping_failure_is_categorical_and_does_not_echo_raw_value() -> None:
    raw = "credential-like-private-value"

    with pytest.raises(PersistenceMappingError) as caught:
        map_universe_snapshot({"members": raw})

    assert raw not in str(caught.value)


def test_dotnet_repositories_reuse_exact_provider_neutral_statements_and_mapping() -> None:
    assert issubclass(
        DotNetUniverseSnapshotRepository,
        SqlAlchemyUniverseSnapshotRepository,
    )
    assert issubclass(
        DotNetDailyFeaturePipelineRunRepository,
        SqlAlchemyDailyFeaturePipelineRunRepository,
    )
