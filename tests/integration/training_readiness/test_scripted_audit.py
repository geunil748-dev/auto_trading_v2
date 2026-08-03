from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, Engine, func, select, text

from auto_trading_v2.adapters.clock import FixedClock
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.dotnet import DotNetUnitOfWorkFactory
from auto_trading_v2.adapters.persistence.tables import (
    BUSINESS_TABLES,
    paper_orders,
    recommendations,
    trade_intents,
)
from auto_trading_v2.application.contracts.training_readiness import (
    RunTrainingReadinessAuditBatchCommand,
)
from auto_trading_v2.application.services.training_readiness import (
    TrainingReadinessAuditService,
)
from auto_trading_v2.domain.training_readiness import (
    COUNTERFACTUAL_PRICE_ONLY_ELIGIBILITY_NOT_DERIVABLE,
    NOT_DERIVABLE_FROM_CURRENT_SCHEMA,
    LegacyCalibrationReadiness,
    MvpTradeModelReadiness,
    PercentageStatus,
)
from tests.integration.training_readiness.synthetic_fixture import (
    persist_datasets,
    seed_synthetic_readiness_data,
)

pytestmark = pytest.mark.integration

EXPECTED_REVISION = "0010_outcome_labels_calibration_dataset"
AUDIT_GENERATED_AT = datetime(2026, 8, 3, 2, tzinfo=UTC)


def test_read_only_training_readiness_audit_and_cross_provider_parity(
    sqlalchemy_uow_factory: SqlAlchemyUnitOfWorkFactory,
    dotnet_uow_factory: DotNetUnitOfWorkFactory,
) -> None:
    datasets = seed_synthetic_readiness_data(sqlalchemy_uow_factory.engine)
    persist_datasets(sqlalchemy_uow_factory, datasets)
    command = RunTrainingReadinessAuditBatchCommand(
        tuple(
            aggregate.dataset.probability_calibration_dataset_id
            for aggregate in (
                datasets.ready,
                datasets.prospective_insufficient,
                datasets.empty,
            )
        )
    )
    before = _table_counts(sqlalchemy_uow_factory.engine)

    sqlalchemy_result = TrainingReadinessAuditService(
        sqlalchemy_uow_factory, FixedClock(AUDIT_GENERATED_AT)
    ).run_batch(command)
    dotnet_result = TrainingReadinessAuditService(
        dotnet_uow_factory, FixedClock(AUDIT_GENERATED_AT)
    ).run_batch(command)

    assert sqlalchemy_result == dotnet_result
    audits = {
        audit.dataset_identity.probability_calibration_dataset_id: audit
        for audit in sqlalchemy_result.audits
    }
    ready = audits[datasets.ready.dataset.probability_calibration_dataset_id.serialize()]
    replay = audits[
        datasets.prospective_insufficient.dataset.probability_calibration_dataset_id.serialize()
    ]
    empty = audits[datasets.empty.dataset.probability_calibration_dataset_id.serialize()]
    _assert_ready_dataset(ready)
    _assert_replay_only_dataset(replay)
    _assert_empty_dataset(empty)

    after = _table_counts(sqlalchemy_uow_factory.engine)
    assert after == before
    assert len(BUSINESS_TABLES) == 25
    with sqlalchemy_uow_factory.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            EXPECTED_REVISION
        )
        assert connection.scalar(select(func.count()).select_from(recommendations)) == 0
        assert connection.scalar(select(func.count()).select_from(trade_intents)) == 0
        assert connection.scalar(select(func.count()).select_from(paper_orders)) == 0


def _assert_ready_dataset(audit: object) -> None:
    included = audit.included_dataset  # type: ignore[attr-defined]
    assert (
        included.total_item_count,
        included.unique_source_session_count,
        included.unique_symbol_listing_count,
    ) == (400, 80, 5)
    assert (included.retrospective_replay_item_count, included.prospective_item_count) == (
        300,
        100,
    )
    assert (included.positive_count, included.not_positive_count) == (200, 200)
    assert (included.replay_positive_count, included.replay_not_positive_count) == (150, 150)
    assert (included.prospective_positive_count, included.prospective_not_positive_count) == (
        50,
        50,
    )
    assert audit.legacy_calibration_readiness.status is LegacyCalibrationReadiness.DATA_READY  # type: ignore[attr-defined]
    assert audit.mvp_trade_model_readiness.status is MvpTradeModelReadiness.NOT_READY  # type: ignore[attr-defined]
    upstream = audit.upstream_quality  # type: ignore[attr-defined]
    decision = audit.data_quality_decision_evidence  # type: ignore[attr-defined]
    assert (upstream.source_scoring_item_count, upstream.scored_ready_count) == (402, 401)
    assert (upstream.scored_degraded_count, upstream.volume_data_incomplete_count) == (1, 1)
    assert upstream.source_feature_snapshot_data_insufficient_count == (
        NOT_DERIVABLE_FROM_CURRENT_SCHEMA
    )
    reasons = {fact.code: fact.count for fact in upstream.exclusion_reason_counts}
    assert reasons["VOLUME_DATA_INCOMPLETE"] == 1
    assert reasons["OTHER_CONTRACT_FAILURE"] == 1
    assert upstream.policy_mismatch_count == 1
    assert (decision.horizon_included_count, decision.horizon_excluded_count) == (400, 2)
    assert (
        decision.source_session_count_before_ready_filter,
        decision.source_session_count_after_ready_filter,
    ) == (82, 80)
    assert (
        decision.symbol_count_before_ready_filter,
        decision.symbol_count_after_ready_filter,
    ) == (
        7,
        5,
    )
    assert decision.price_only_eligibility == (COUNTERFACTUAL_PRICE_ONLY_ELIGIBILITY_NOT_DERIVABLE)


def _assert_replay_only_dataset(audit: object) -> None:
    included = audit.included_dataset  # type: ignore[attr-defined]
    assert (included.total_item_count, included.retrospective_replay_item_count) == (300, 300)
    assert included.prospective_item_count == 0
    assert audit.legacy_calibration_readiness.status is (  # type: ignore[attr-defined]
        LegacyCalibrationReadiness.PROSPECTIVE_INSUFFICIENT
    )
    decision = audit.data_quality_decision_evidence  # type: ignore[attr-defined]
    assert (decision.horizon_included_count, decision.horizon_excluded_count) == (300, 0)


def _assert_empty_dataset(audit: object) -> None:
    assert audit.included_dataset.total_item_count == 0  # type: ignore[attr-defined]
    assert audit.upstream_quality.source_scoring_item_count == 0  # type: ignore[attr-defined]
    assert audit.legacy_calibration_readiness.status is (  # type: ignore[attr-defined]
        LegacyCalibrationReadiness.DATA_INSUFFICIENT
    )
    assert audit.data_quality_decision_evidence.volume_only_excluded.status is (  # type: ignore[attr-defined]
        PercentageStatus.ZERO_DENOMINATOR
    )


def _table_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {table.fullname: _count(connection, table) for table in BUSINESS_TABLES}


def _count(connection: Connection, table: object) -> int:
    value = connection.scalar(select(func.count()).select_from(table))  # type: ignore[arg-type]
    assert value is not None
    return int(value)
