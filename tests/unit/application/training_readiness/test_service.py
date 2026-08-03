from dataclasses import replace
from decimal import Decimal

import pytest

from auto_trading_v2.application.contracts.training_readiness import (
    RunTrainingReadinessAuditBatchCommand,
    RunTrainingReadinessAuditCommand,
)
from auto_trading_v2.application.services.training_readiness import (
    TrainingReadinessAuditService,
)
from auto_trading_v2.application.services.training_readiness_analysis import (
    analyze_upstream_lineage,
)
from auto_trading_v2.application.training_readiness_errors import (
    TrainingReadinessDatasetNotFoundError,
)
from auto_trading_v2.domain.training_readiness import (
    NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
    MvpTradeModelReadiness,
)
from tests.unit.training_readiness_helpers import (
    FakeRepository,
    FakeUnitOfWorkFactory,
    aggregate,
    lineage_record,
    service_context,
)


def test_service_reads_one_explicit_dataset_and_never_commits_or_writes() -> None:
    service, factory, value = service_context()

    result = service.run(
        RunTrainingReadinessAuditCommand(value.dataset.probability_calibration_dataset_id)
    )

    assert result.included_dataset.total_item_count == 2
    assert result.mvp_trade_model_readiness.status is MvpTradeModelReadiness.NOT_READY
    assert "EXECUTION_ALIGNED_OUTCOME_POLICY_MISSING" in (result.mvp_trade_model_readiness.blockers)
    assert factory.repository.reads == 3
    assert factory.repository.writes == 0
    assert factory.commits == 0
    assert factory.rollbacks == 1


def test_missing_dataset_is_safe_and_batch_groups_explicit_ids() -> None:
    missing_factory = FakeUnitOfWorkFactory(FakeRepository(None))
    service, _, value = service_context()
    missing = TrainingReadinessAuditService(
        missing_factory,
        service.clock,  # type: ignore[arg-type]
    )

    with pytest.raises(TrainingReadinessDatasetNotFoundError):
        missing.run(
            RunTrainingReadinessAuditCommand(value.dataset.probability_calibration_dataset_id)
        )
    batch = service.run_batch(
        RunTrainingReadinessAuditBatchCommand((value.dataset.probability_calibration_dataset_id,))
    )

    assert batch.horizon_groups[0].horizon_trading_days == 1
    assert batch.horizon_groups[0].dataset_ids == (
        value.dataset.probability_calibration_dataset_id.serialize(),
    )
    assert missing_factory.commits == 0


def test_upstream_quality_reasons_and_not_derivable_fields_are_explicit() -> None:
    value = aggregate()
    included = lineage_record(value.items[0])
    volume = replace(
        lineage_record(value.items[1]),
        source_daily_feature_scoring_item_id=value.items[1].source_daily_feature_scoring_item_id,
        scoring_outcome="SCORED_DEGRADED",
        source_quality_status="DEGRADED",
        pipeline_outcome="DEGRADED",
        feature_quality_status="DEGRADED",
        quality_reason_codes=("VOLUME_DATA_INCOMPLETE",),
        overall_relative_score=Decimal("60"),
    )
    missing_score = replace(
        volume,
        source_daily_feature_scoring_item_id=(value.items[1].source_daily_feature_scoring_item_id),
        scoring_outcome="SCORED_READY",
        source_quality_status="READY",
        feature_quality_status="READY",
        quality_reason_codes=(),
        overall_relative_score=None,
    )

    upstream, decision, not_derivable = analyze_upstream_lineage(
        value.dataset, (value.items[0],), (included, volume, missing_score)
    )
    reasons = {fact.code: fact.count for fact in upstream.exclusion_reason_counts}

    assert reasons["VOLUME_DATA_INCOMPLETE"] == 1
    assert reasons["MISSING_SCORE"] == 1
    assert upstream.source_feature_snapshot_data_insufficient_count == (
        NOT_DERIVABLE_FROM_CURRENT_SCHEMA
    )
    assert upstream.price_only_v2_eligible_count == 3
    assert upstream.price_only_v2_ineligible_count == 0
    assert decision.price_only_eligibility.percentage == "100.000000"
    assert "counterfactual_price_only_eligibility_percentage" not in not_derivable
