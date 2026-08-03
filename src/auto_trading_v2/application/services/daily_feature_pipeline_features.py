"""Explicit feature-policy dispatch for the daily feature pipeline."""

from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    RunDailyFeaturePipelineCommand,
)
from auto_trading_v2.application.feature_building import (
    BuildDailyPriceTechnicalFeatureSnapshotCommand,
    BuildDailyTechnicalFeatureSnapshotCommand,
    DailyTechnicalFeatureSnapshotBuildResult,
)
from auto_trading_v2.application.services.daily_price_technical_feature_snapshot import (
    DailyPriceTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.daily_technical_feature_snapshot import (
    DailyTechnicalFeatureSnapshotService,
)
from auto_trading_v2.domain.feature_pipeline import (
    DAILY_FEATURE_PIPELINE_POLICY_V2,
    DailyFeaturePipelinePolicy,
)
from auto_trading_v2.domain.universes import UniverseMember


def build_pipeline_feature_snapshot(
    member: UniverseMember,
    command: RunDailyFeaturePipelineCommand,
    policy: DailyFeaturePipelinePolicy,
    v1_service: DailyTechnicalFeatureSnapshotService,
    v2_service: DailyPriceTechnicalFeatureSnapshotService | None,
) -> DailyTechnicalFeatureSnapshotBuildResult:
    if policy == DAILY_FEATURE_PIPELINE_POLICY_V2:
        if v2_service is None:
            raise RuntimeError("price-only feature service is unavailable")
        return v2_service.build(
            BuildDailyPriceTechnicalFeatureSnapshotCommand(
                command.provider_code,
                member.symbol,
                command.as_of,
                command.horizon,
            )
        )
    return v1_service.build(
        BuildDailyTechnicalFeatureSnapshotCommand(
            command.provider_code,
            member.symbol,
            command.as_of,
            command.horizon,
        )
    )
