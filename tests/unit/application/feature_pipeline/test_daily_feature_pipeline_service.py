from datetime import UTC, datetime

import pytest

from auto_trading_v2.adapters.market_data.twelve_data import TwelveDataErrorCategory
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    DailyFeaturePipelineExecutionOutcome,
    RunDailyFeaturePipelineCommand,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataIngestionOutcome,
)
from auto_trading_v2.application.ports.batch_budget import DailyMarketDataProviderRole
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus

from .fakes import FakeBudget, command, service, universe


def outcomes(result: object) -> tuple[DailyFeaturePipelineItemOutcome, ...]:
    return tuple(item.outcome for item in result.result.items)


def test_three_symbols_execute_in_canonical_order_with_ready_and_degraded() -> None:
    snapshot = universe("NVDA", "MSFT", "AAPL")
    context = service(snapshot)
    context.features.scripts["MSFT"] = FeatureQualityStatus.DEGRADED

    result = context.service.run(command(snapshot))

    assert result.outcome is DailyFeaturePipelineExecutionOutcome.EXECUTED
    assert result.result.run.status is DailyFeaturePipelineRunStatus.COMPLETED
    assert context.ingestion.calls == ["AAPL", "MSFT", "NVDA"]
    assert context.features.calls == ["AAPL", "MSFT", "NVDA"]
    assert outcomes(result) == (
        DailyFeaturePipelineItemOutcome.READY,
        DailyFeaturePipelineItemOutcome.DEGRADED,
        DailyFeaturePipelineItemOutcome.READY,
    )
    assert all(code == "TWELVE_DATA_TIME_SERIES" for code in context.ingestion.source_codes)


@pytest.mark.parametrize(
    ("ingestion_outcome", "feature_quality", "expected"),
    (
        (
            TwelveDataIngestionOutcome.NO_DATA,
            FeatureQualityStatus.READY,
            DailyFeaturePipelineItemOutcome.NO_DATA,
        ),
        (
            TwelveDataIngestionOutcome.COMPLETED,
            None,
            DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT,
        ),
    ),
)
def test_nonfatal_data_gap_isolated_as_warning(
    ingestion_outcome: TwelveDataIngestionOutcome,
    feature_quality: FeatureQualityStatus | None,
    expected: DailyFeaturePipelineItemOutcome,
) -> None:
    snapshot = universe("AAPL", "MSFT")
    context = service(snapshot)
    context.ingestion.scripts["AAPL"] = (ingestion_outcome, None)
    context.features.scripts["AAPL"] = feature_quality

    result = context.service.run(command(snapshot))

    assert outcomes(result)[0] is expected
    assert outcomes(result)[1] is DailyFeaturePipelineItemOutcome.READY
    assert result.result.run.status is DailyFeaturePipelineRunStatus.COMPLETED_WITH_WARNINGS


def test_symbol_provider_error_does_not_stop_following_symbol() -> None:
    snapshot = universe("AAPL", "MSFT")
    context = service(snapshot)
    context.ingestion.scripts["AAPL"] = (
        TwelveDataIngestionOutcome.PROVIDER_ERROR,
        TwelveDataErrorCategory.INSTRUMENT_NOT_FOUND.value,
    )

    result = context.service.run(command(snapshot))

    assert context.ingestion.calls == ["AAPL", "MSFT"]
    assert outcomes(result) == (
        DailyFeaturePipelineItemOutcome.PROVIDER_ERROR,
        DailyFeaturePipelineItemOutcome.READY,
    )
    assert result.result.run.status is DailyFeaturePipelineRunStatus.COMPLETED_WITH_PARTIAL_FAILURES


def test_authentication_failure_aborts_remaining_symbols_without_more_requests() -> None:
    snapshot = universe("AAPL", "MSFT", "NVDA")
    context = service(snapshot)
    context.ingestion.scripts["AAPL"] = (
        TwelveDataIngestionOutcome.PROVIDER_ERROR,
        TwelveDataErrorCategory.AUTHENTICATION_REJECTED.value,
    )

    result = context.service.run(command(snapshot))

    assert context.ingestion.calls == ["AAPL"]
    assert outcomes(result) == (
        DailyFeaturePipelineItemOutcome.PROVIDER_ERROR,
        DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED,
        DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED,
    )
    assert result.result.run.status is DailyFeaturePipelineRunStatus.ABORTED_PROVIDER_FATAL


def test_budget_preflight_blocks_all_network_bar_and_feature_work() -> None:
    snapshot = universe("AAPL", "MSFT", "NVDA")
    context = service(snapshot, FakeBudget(daily_available=2))

    result = context.service.run(command(snapshot))

    assert result.result.run.status is DailyFeaturePipelineRunStatus.BUDGET_BLOCKED
    assert outcomes(result) == (DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET,) * 3
    assert context.ingestion.calls == []
    assert context.features.calls == []


def test_validation_only_provider_role_is_rejected_without_network() -> None:
    snapshot = universe("AAPL")
    context = service(
        snapshot,
        FakeBudget(provider_role=DailyMarketDataProviderRole.VALIDATION_ONLY),
    )

    result = context.service.run(command(snapshot))

    assert result.result.run.status is DailyFeaturePipelineRunStatus.ABORTED_PROVIDER_FATAL
    assert result.result.items[0].safe_reason_code == "PROVIDER_ROLE_UNSUPPORTED"
    assert context.ingestion.calls == []


def test_three_consecutive_transient_failures_open_bounded_circuit() -> None:
    snapshot = universe("AAPL", "AMZN", "MSFT", "NVDA")
    context = service(snapshot)
    for symbol in ("AAPL", "AMZN", "MSFT"):
        context.ingestion.scripts[symbol] = (
            TwelveDataIngestionOutcome.PROVIDER_ERROR,
            TwelveDataErrorCategory.HTTP_TIMEOUT.value,
        )

    result = context.service.run(command(snapshot))

    assert context.ingestion.calls == ["AAPL", "AMZN", "MSFT"]
    assert outcomes(result)[-1] is DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED
    assert result.result.items[-1].safe_reason_code == "TRANSIENT_FAILURE_CIRCUIT_OPEN"


def test_mid_run_daily_budget_exhaustion_marks_current_and_remaining_items() -> None:
    snapshot = universe("AAPL", "MSFT", "NVDA")
    context = service(snapshot)
    context.ingestion.scripts["MSFT"] = (
        TwelveDataIngestionOutcome.CREDIT_BUDGET_EXHAUSTED,
        TwelveDataErrorCategory.DAILY_CREDIT_BUDGET_EXHAUSTED.value,
    )

    result = context.service.run(command(snapshot))

    assert context.ingestion.calls == ["AAPL", "MSFT"]
    assert outcomes(result) == (
        DailyFeaturePipelineItemOutcome.READY,
        DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET,
        DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET,
    )


def test_exact_retry_reuses_run_without_ids_network_bar_or_feature_build() -> None:
    snapshot = universe("AAPL", "MSFT")
    context = service(snapshot)
    first = context.service.run(command(snapshot))
    observed = (
        context.run_ids.calls,
        context.item_ids.calls,
        len(context.ingestion.calls),
        len(context.features.calls),
        context.factory.runs.add_calls,
    )

    second = context.service.run(command(snapshot))

    assert second.outcome is DailyFeaturePipelineExecutionOutcome.ALREADY_EXISTS
    assert second.result == first.result
    assert observed == (
        context.run_ids.calls,
        context.item_ids.calls,
        len(context.ingestion.calls),
        len(context.features.calls),
        context.factory.runs.add_calls,
    )


def test_no_completed_session_and_out_of_coverage_are_network_free() -> None:
    snapshot = universe("AAPL")
    no_session = service(snapshot)
    before_first_close = datetime(2026, 1, 1, 12, tzinfo=UTC)
    no_session_result = no_session.service.run(command(snapshot, as_of=before_first_close))
    outside = service(snapshot)
    outside_result = outside.service.run(command(snapshot, as_of=datetime(2027, 1, 2, tzinfo=UTC)))

    assert no_session_result.result.run.status is DailyFeaturePipelineRunStatus.NO_COMPLETED_SESSION
    assert outside_result.result.run.status is DailyFeaturePipelineRunStatus.ABORTED_PROVIDER_FATAL
    assert no_session.ingestion.calls == []
    assert outside.ingestion.calls == []


def test_command_rejects_non_primary_provider_code_at_run_preflight() -> None:
    snapshot = universe("AAPL")
    context = service(snapshot)
    source = command(snapshot)
    alpaca = RunDailyFeaturePipelineCommand(
        source.universe_snapshot_id,
        "ALPACA_IEX_STOCK_BARS",
        source.as_of,
        source.completion_grace,
        source.horizon,
        source.requested_session_count,
    )

    result = context.service.run(alpaca)

    assert result.result.run.status is DailyFeaturePipelineRunStatus.ABORTED_PROVIDER_FATAL
    assert result.result.items[0].safe_reason_code == "PROVIDER_CODE_UNSUPPORTED"
    assert context.ingestion.calls == []
