"""Read-only application service for one explicit P4B.2A dataset."""

from dataclasses import dataclass

from auto_trading_v2.application.contracts.training_readiness import (
    RunTrainingReadinessAuditBatchCommand,
    RunTrainingReadinessAuditCommand,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.application.services.training_readiness_analysis import (
    analyze_upstream_lineage,
    dataset_identity_facts,
)
from auto_trading_v2.application.training_readiness_errors import (
    TrainingReadinessDatasetNotFoundError,
)
from auto_trading_v2.domain.primitives.time import normalize_utc
from auto_trading_v2.domain.training_readiness import (
    MVP_TRADE_MODEL_BLOCKERS,
    HorizonAuditGroup,
    MvpTradeModelReadiness,
    MvpTradeModelReadinessResult,
    TrainingReadinessAuditBatchResult,
    TrainingReadinessAuditResult,
    evaluate_legacy_calibration_readiness,
    included_dataset_facts,
)
from auto_trading_v2.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class TrainingReadinessAuditService:
    unit_of_work_factory: UnitOfWorkFactory
    clock: Clock

    def run(self, command: RunTrainingReadinessAuditCommand) -> TrainingReadinessAuditResult:
        return self._run_at(command, normalize_utc(self.clock.now_utc()))

    def run_batch(
        self, command: RunTrainingReadinessAuditBatchCommand
    ) -> TrainingReadinessAuditBatchResult:
        generated_at = normalize_utc(self.clock.now_utc())
        commands = tuple(
            RunTrainingReadinessAuditCommand(identifier)
            for identifier in sorted(
                command.probability_calibration_dataset_ids,
                key=lambda value: value.serialize(),
            )
        )
        audits = tuple(self._run_at(item, generated_at) for item in commands)
        horizons = sorted({audit.dataset_identity.horizon_trading_days for audit in audits})
        groups = tuple(
            HorizonAuditGroup(
                horizon,
                tuple(
                    audit.dataset_identity.probability_calibration_dataset_id
                    for audit in audits
                    if audit.dataset_identity.horizon_trading_days == horizon
                ),
                sum(
                    audit.data_quality_decision_evidence.horizon_included_count
                    for audit in audits
                    if audit.dataset_identity.horizon_trading_days == horizon
                ),
                sum(
                    audit.data_quality_decision_evidence.horizon_excluded_count
                    for audit in audits
                    if audit.dataset_identity.horizon_trading_days == horizon
                ),
            )
            for horizon in horizons
        )
        return TrainingReadinessAuditBatchResult(generated_at, audits, groups)

    def _run_at(
        self,
        command: RunTrainingReadinessAuditCommand,
        generated_at: object,
    ) -> TrainingReadinessAuditResult:
        with self.unit_of_work_factory() as unit_of_work:
            repository = unit_of_work.probability_calibration_datasets
            dataset = repository.get_by_id(command.probability_calibration_dataset_id)
            if dataset is None:
                raise TrainingReadinessDatasetNotFoundError()
            items = repository.list_items(command.probability_calibration_dataset_id)
            lineage = repository.list_training_readiness_lineage(dataset)
        included = included_dataset_facts(dataset, items)
        upstream, decision, not_derivable = analyze_upstream_lineage(dataset, items, lineage)
        legacy = evaluate_legacy_calibration_readiness(dataset, included)
        mvp = MvpTradeModelReadinessResult(
            MvpTradeModelReadiness.NOT_READY, MVP_TRADE_MODEL_BLOCKERS
        )
        conclusion = (
            f"{legacy.status.value}; {mvp.status.value}. "
            "Resolve the evidence-backed data-quality and executable-outcome blockers "
            "before fitting a probability model."
        )
        return TrainingReadinessAuditResult(
            audit_generated_at=normalize_utc(generated_at),  # type: ignore[arg-type]
            dataset_identity=dataset_identity_facts(dataset),
            included_dataset=included,
            upstream_quality=upstream,
            legacy_calibration_readiness=legacy,
            mvp_trade_model_readiness=mvp,
            data_quality_decision_evidence=decision,
            not_derivable_fields=not_derivable,
            conclusion=conclusion,
        )
