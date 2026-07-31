"""Canonical-order sequential symbol executor for the P3 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.application.contracts.completed_daily_bars import (
    CompletedDailyBarsRequestCreationResult,
)
from auto_trading_v2.application.contracts.daily_feature_pipeline import (
    NewDailyFeaturePipelineItem,
    RunDailyFeaturePipelineCommand,
)
from auto_trading_v2.application.contracts.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionCommand,
)
from auto_trading_v2.application.errors import PersistenceError
from auto_trading_v2.application.feature_building import (
    BuildDailyTechnicalFeatureSnapshotCommand,
    DailyTechnicalFeatureSnapshotBuildOutcome,
)
from auto_trading_v2.application.ports.batch_budget import DailyMarketDataBatchBudgetPort
from auto_trading_v2.application.ports.id_factory import (
    DailyFeaturePipelineItemIDFactory,
)
from auto_trading_v2.application.services.daily_feature_pipeline_policy import (
    ingestion_item_outcome,
)
from auto_trading_v2.application.services.daily_technical_feature_snapshot import (
    DailyTechnicalFeatureSnapshotService,
)
from auto_trading_v2.application.services.twelve_data_ingestion import (
    TwelveDataDailyMarketBarIngestionService,
)
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_pipeline import DailyFeaturePipelineItemOutcome
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus
from auto_trading_v2.domain.primitives import DailyFeaturePipelineRunID, FeatureSnapshotID
from auto_trading_v2.domain.universes import UniverseMember
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class PreparedPipelineMember:
    member: UniverseMember
    result: CompletedDailyBarsRequestCreationResult


@dataclass(frozen=True, slots=True)
class SequentialDailyFeaturePipelineExecutor:
    budget: DailyMarketDataBatchBudgetPort
    ingestion_service: TwelveDataDailyMarketBarIngestionService
    feature_service: DailyTechnicalFeatureSnapshotService
    clock: Clock
    item_id_factory: DailyFeaturePipelineItemIDFactory
    transient_failure_limit: int

    def execute(
        self,
        run_id: DailyFeaturePipelineRunID,
        prepared: tuple[PreparedPipelineMember, ...],
        command: RunDailyFeaturePipelineCommand,
    ) -> tuple[tuple[NewDailyFeaturePipelineItem, ...], bool]:
        items: list[NewDailyFeaturePipelineItem] = []
        transient_failures = 0
        abort_reason: str | None = None
        budget_exhausted = False
        fatal = False
        for ordinal, entry in enumerate(prepared, 1):
            if abort_reason is not None:
                outcome = (
                    DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET
                    if budget_exhausted
                    else DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_ABORTED
                )
                items.append(self.item(run_id, ordinal, entry, outcome, abort_reason))
                continue
            if entry.result.request is None:
                items.append(
                    self.item(
                        run_id,
                        ordinal,
                        entry,
                        DailyFeaturePipelineItemOutcome.CALENDAR_ERROR,
                        entry.result.safe_reason_code or "CALENDAR_ERROR",
                    )
                )
                continue
            before = self.budget.consumed_daily_credits()
            started = self.clock.now_utc()
            completed_session = entry.result.request.completed_through_session_date
            if completed_session is None:
                items.append(
                    self.item(
                        run_id,
                        ordinal,
                        entry,
                        DailyFeaturePipelineItemOutcome.CALENDAR_ERROR,
                        "CALENDAR_SESSION_MISSING",
                        started_at=started,
                    )
                )
                continue
            ingestion_command = TwelveDataDailyMarketBarIngestionCommand(
                entry.member.symbol,
                entry.member.mic_code,
                DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
                completed_session,
                command.requested_session_count,
            )
            try:
                ingested = self.ingestion_service.ingest_request(
                    ingestion_command,
                    entry.result.request,
                )
            except PersistenceError:
                fatal = True
                abort_reason = "PERSISTENCE_INFRASTRUCTURE_UNAVAILABLE"
                items.append(
                    self.item(
                        run_id,
                        ordinal,
                        entry,
                        DailyFeaturePipelineItemOutcome.PROVIDER_ERROR,
                        abort_reason,
                        started_at=started,
                        provider_requests=1,
                    )
                )
                continue
            credits = credit_delta(before, self.budget.consumed_daily_credits())
            item_outcome, reason, provider_fatal, transient = ingestion_item_outcome(ingested)
            if item_outcome is not None:
                transient_failures = transient_failures + 1 if transient else 0
                items.append(
                    self.item(
                        run_id,
                        ordinal,
                        entry,
                        item_outcome,
                        reason,
                        created=ingested.summary.created_count,
                        existing=ingested.summary.existing_count,
                        started_at=started,
                        provider_requests=1,
                        provider_credits=credits,
                    )
                )
                if item_outcome is DailyFeaturePipelineItemOutcome.NOT_ATTEMPTED_BUDGET:
                    budget_exhausted = True
                    abort_reason = reason
                elif provider_fatal:
                    fatal = True
                    abort_reason = reason
                elif transient_failures >= self.transient_failure_limit:
                    abort_reason = "TRANSIENT_FAILURE_CIRCUIT_OPEN"
                continue
            transient_failures = 0
            try:
                built = self.feature_service.build(
                    BuildDailyTechnicalFeatureSnapshotCommand(
                        source_code=command.provider_code,
                        symbol=entry.member.symbol,
                        as_of=command.as_of,
                        horizon=command.horizon,
                    )
                )
            except PersistenceError:
                fatal = True
                abort_reason = "PERSISTENCE_INFRASTRUCTURE_UNAVAILABLE"
                items.append(
                    self.item(
                        run_id,
                        ordinal,
                        entry,
                        DailyFeaturePipelineItemOutcome.PROVIDER_ERROR,
                        abort_reason,
                        created=ingested.summary.created_count,
                        existing=ingested.summary.existing_count,
                        started_at=started,
                        provider_requests=1,
                        provider_credits=credits,
                    )
                )
                continue
            if built.outcome is DailyTechnicalFeatureSnapshotBuildOutcome.DATA_INSUFFICIENT:
                items.append(
                    self.item(
                        run_id,
                        ordinal,
                        entry,
                        DailyFeaturePipelineItemOutcome.DATA_INSUFFICIENT,
                        built.reason_codes[0] if built.reason_codes else "DATA_INSUFFICIENT",
                        created=ingested.summary.created_count,
                        existing=ingested.summary.existing_count,
                        started_at=started,
                        provider_requests=1,
                        provider_credits=credits,
                    )
                )
                continue
            snapshot = built.snapshot
            if snapshot is None:
                raise RuntimeError("feature build result is inconsistent")
            quality = snapshot.snapshot_input.quality_status
            outcome = (
                DailyFeaturePipelineItemOutcome.READY
                if quality is FeatureQualityStatus.READY
                else DailyFeaturePipelineItemOutcome.DEGRADED
            )
            items.append(
                self.item(
                    run_id,
                    ordinal,
                    entry,
                    outcome,
                    None,
                    created=ingested.summary.created_count,
                    existing=ingested.summary.existing_count,
                    snapshot=snapshot.feature_snapshot_id,
                    quality=quality,
                    started_at=started,
                    provider_requests=1,
                    provider_credits=credits,
                )
            )
        return tuple(items), fatal

    def not_attempted(
        self,
        run_id: DailyFeaturePipelineRunID,
        prepared: tuple[PreparedPipelineMember, ...],
        outcome: DailyFeaturePipelineItemOutcome,
        reason: str,
    ) -> tuple[NewDailyFeaturePipelineItem, ...]:
        return tuple(
            self.item(run_id, ordinal, entry, outcome, reason)
            for ordinal, entry in enumerate(prepared, 1)
        )

    def item(
        self,
        run_id: DailyFeaturePipelineRunID,
        ordinal: int,
        entry: PreparedPipelineMember,
        outcome: DailyFeaturePipelineItemOutcome,
        reason: str | None,
        *,
        created: int = 0,
        existing: int = 0,
        snapshot: FeatureSnapshotID | None = None,
        quality: FeatureQualityStatus | None = None,
        started_at: datetime | None = None,
        provider_requests: int = 0,
        provider_credits: int | None = None,
    ) -> NewDailyFeaturePipelineItem:
        started = self.clock.now_utc() if started_at is None else started_at
        request = entry.result.request
        return NewDailyFeaturePipelineItem(
            self.item_id_factory.new(),
            run_id,
            ordinal,
            entry.member.symbol,
            entry.member.mic_code,
            None if request is None else request.completed_through_session_date,
            outcome,
            created,
            existing,
            snapshot,
            quality,
            reason,
            provider_requests,
            provider_credits,
            started,
            self.clock.now_utc(),
        )


def credit_delta(before: int | None, after: int | None) -> int | None:
    if before is None or after is None or after < before:
        return None
    return after - before
