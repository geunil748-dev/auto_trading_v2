"""Insert-only P4B.2A label persistence with unique-race resolution."""

from dataclasses import dataclass
from enum import StrEnum

from auto_trading_v2.application.contracts.outcome_labels import NewDailyFeatureOutcomeLabel
from auto_trading_v2.application.errors import DuplicateRecordError, PersistenceError
from auto_trading_v2.application.outcome_label_errors import (
    DailyFeatureOutcomeLabelConflictError,
    DailyFeatureOutcomeLabelPersistenceError,
    DailyFeatureOutcomeLabelRaceResolutionError,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory
from auto_trading_v2.domain.outcome_labels import DailyFeatureOutcomeLabel


class CanonicalLabelStoreDisposition(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class CanonicalLabelStoreResult:
    disposition: CanonicalLabelStoreDisposition
    label: DailyFeatureOutcomeLabel


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeLabelStore:
    unit_of_work_factory: UnitOfWorkFactory

    def existing(self, label_key: str) -> DailyFeatureOutcomeLabel | None:
        with self.unit_of_work_factory() as unit_of_work:
            return unit_of_work.daily_feature_outcome_labels.get_by_label_key(label_key)

    def persist(self, candidate: NewDailyFeatureOutcomeLabel) -> CanonicalLabelStoreResult:
        existing = self.existing(candidate.label.label_key)
        if existing is not None:
            return self._same(existing, candidate)
        try:
            with self.unit_of_work_factory() as unit_of_work:
                try:
                    stored = unit_of_work.daily_feature_outcome_labels.add(candidate)
                except DuplicateRecordError:
                    unit_of_work.rollback()
                else:
                    unit_of_work.commit()
                    return CanonicalLabelStoreResult(CanonicalLabelStoreDisposition.CREATED, stored)
        except PersistenceError:
            raise DailyFeatureOutcomeLabelPersistenceError() from None
        existing = self.existing(candidate.label.label_key)
        if existing is None:
            raise DailyFeatureOutcomeLabelRaceResolutionError()
        return self._same(existing, candidate)

    @staticmethod
    def _same(
        existing: DailyFeatureOutcomeLabel,
        candidate: NewDailyFeatureOutcomeLabel,
    ) -> CanonicalLabelStoreResult:
        if existing.content_digest != candidate.label.content_digest:
            raise DailyFeatureOutcomeLabelConflictError()
        return CanonicalLabelStoreResult(CanonicalLabelStoreDisposition.ALREADY_EXISTS, existing)
