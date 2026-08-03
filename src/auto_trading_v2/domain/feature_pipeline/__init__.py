"""Canonical multi-symbol daily feature pipeline domain."""

from auto_trading_v2.domain.feature_pipeline.errors import (
    DailyFeaturePipelineValidationError,
)
from auto_trading_v2.domain.feature_pipeline.identity import (
    DEFAULT_REQUESTED_SESSIONS,
    FEATURE_SET_CODE,
    FEATURE_SET_VERSION,
    MIN_REQUESTED_SESSIONS,
    PIPELINE_CODE,
    PIPELINE_VERSION,
    TRANSIENT_FAILURE_LIMIT,
    DailyFeaturePipelineIdentity,
    daily_feature_run_key,
    pipeline_content_digest,
)
from auto_trading_v2.domain.feature_pipeline.models import (
    DailyFeaturePipelineItem,
    DailyFeaturePipelineRun,
    DailyFeaturePipelineRunWithItems,
    daily_feature_pipeline_content_digest,
)
from auto_trading_v2.domain.feature_pipeline.outcomes import (
    DailyFeaturePipelineItemOutcome,
    DailyFeaturePipelineRunStatus,
)

__all__ = [
    "DEFAULT_REQUESTED_SESSIONS",
    "FEATURE_SET_CODE",
    "FEATURE_SET_VERSION",
    "MIN_REQUESTED_SESSIONS",
    "PIPELINE_CODE",
    "PIPELINE_VERSION",
    "TRANSIENT_FAILURE_LIMIT",
    "DailyFeaturePipelineIdentity",
    "DailyFeaturePipelineItem",
    "DailyFeaturePipelineItemOutcome",
    "DailyFeaturePipelineRun",
    "DailyFeaturePipelineRunStatus",
    "DailyFeaturePipelineRunWithItems",
    "DailyFeaturePipelineValidationError",
    "daily_feature_pipeline_content_digest",
    "daily_feature_run_key",
    "pipeline_content_digest",
]
