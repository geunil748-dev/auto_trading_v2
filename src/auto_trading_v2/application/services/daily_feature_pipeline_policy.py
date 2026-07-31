"""Deterministic P3 budget and failure-classification policy."""

from __future__ import annotations

from collections import Counter

from auto_trading_v2.adapters.market_data.twelve_data import TwelveDataErrorCategory
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataIngestionOutcome,
    TwelveDataIngestionResult,
)
from auto_trading_v2.application.ports.batch_budget import (
    DailyMarketDataBatchBudgetAssessment,
    DailyMarketDataBatchBudgetPort,
)
from auto_trading_v2.domain.feature_pipeline import (
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
)

_FATAL = frozenset(
    {
        TwelveDataErrorCategory.PROVIDER_DISABLED.value,
        TwelveDataErrorCategory.CONFIGURATION_MISSING.value,
        TwelveDataErrorCategory.CONFIGURATION_INVALID.value,
        TwelveDataErrorCategory.AUTHENTICATION_REJECTED.value,
        TwelveDataErrorCategory.ACCESS_FORBIDDEN.value,
        TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID.value,
    }
)
_TRANSIENT = frozenset(
    {
        TwelveDataErrorCategory.HTTP_TIMEOUT.value,
        TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE.value,
        TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT.value,
    }
)


def assess_budget(
    budget: DailyMarketDataBatchBudgetPort,
    member_count: int,
    requested_session_count: int,
) -> DailyMarketDataBatchBudgetAssessment:
    estimated = budget.estimate_maximum_cost(member_count, requested_session_count)
    daily = budget.available_daily_budget()
    minute = budget.available_minute_budget()
    known = estimated is not None and daily is not None
    can_start = estimated is not None and daily is not None and estimated <= daily
    return DailyMarketDataBatchBudgetAssessment(
        provider_code=budget.provider_code,
        estimated_credits=estimated,
        available_daily_credits=daily,
        available_minute_credits=minute,
        budget_known=known,
        can_start=can_start,
    )


def ingestion_item_outcome(
    result: TwelveDataIngestionResult,
) -> tuple[DailyFeaturePipelineItemOutcome | None, str | None, bool, bool]:
    """Return item outcome, safe reason, fatal flag, transient flag."""

    category = result.summary.safe_error_category
    if result.outcome in {
        TwelveDataIngestionOutcome.COMPLETED,
        TwelveDataIngestionOutcome.COMPLETED_WITH_EXISTING,
    }:
        return None, None, False, False
    if result.outcome is TwelveDataIngestionOutcome.NO_DATA:
        return DailyFeaturePipelineItemOutcome.NO_DATA, "NO_DATA", False, False
    if result.outcome is TwelveDataIngestionOutcome.CREDIT_BUDGET_EXHAUSTED:
        return (
            DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET,
            TwelveDataErrorCategory.DAILY_CREDIT_BUDGET_EXHAUSTED.value,
            False,
            False,
        )
    safe = category or "PROVIDER_ERROR"
    fatal = (
        result.outcome
        in {
            TwelveDataIngestionOutcome.PROVIDER_DISABLED,
            TwelveDataIngestionOutcome.PROVIDER_CONFIGURATION_MISSING,
        }
        or safe in _FATAL
    )
    return DailyFeaturePipelineItemOutcome.PROVIDER_ERROR, safe, fatal, safe in _TRANSIENT


def outcome_counts(
    outcomes: tuple[DailyFeaturePipelineItemOutcome, ...],
) -> dict[str, int]:
    values = Counter(outcomes)
    return {
        "ready_count": values[DailyFeaturePipelineItemOutcome.READY],
        "degraded_count": values[DailyFeaturePipelineItemOutcome.DEGRADED],
        "data_insufficient_count": values[DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT],
        "no_data_count": values[DailyFeaturePipelineItemOutcome.NO_DATA],
        "provider_error_count": values[DailyFeaturePipelineItemOutcome.PROVIDER_ERROR],
        "calendar_error_count": values[DailyFeaturePipelineItemOutcome.CALENDAR_ERROR],
        "not_attempted_count": values[DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET]
        + values[DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED],
    }


def completed_run_status(
    outcomes: tuple[DailyFeaturePipelineItemOutcome, ...],
) -> DailyFeaturePipelineRunStatus:
    if any(
        value
        in {
            DailyFeaturePipelineItemOutcome.PROVIDER_ERROR,
            DailyFeaturePipelineItemOutcome.CALENDAR_ERROR,
            DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET,
            DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED,
        }
        for value in outcomes
    ):
        return DailyFeaturePipelineRunStatus.COMPLETED_WITH_PARTIAL_FAILURES
    if any(
        value
        in {
            DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT,
            DailyFeaturePipelineItemOutcome.NO_DATA,
        }
        for value in outcomes
    ):
        return DailyFeaturePipelineRunStatus.COMPLETED_WITH_WARNINGS
    return DailyFeaturePipelineRunStatus.COMPLETED
