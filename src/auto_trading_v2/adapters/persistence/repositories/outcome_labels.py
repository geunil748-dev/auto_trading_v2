"""SQLAlchemy Core repository for immutable P4B.2A outcome labels."""

from collections.abc import Callable

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.outcome_label_mapping import (
    map_daily_feature_outcome_label,
    new_daily_feature_outcome_label_values,
)
from auto_trading_v2.adapters.persistence.tables import daily_feature_outcome_labels
from auto_trading_v2.application.contracts.outcome_labels import NewDailyFeatureOutcomeLabel
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.outcome_labels import DailyFeatureOutcomeLabel
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureOutcomeLabelID,
    DailyFeatureScoringItemID,
)


def _allow_operation() -> None:
    return None


class SqlAlchemyDailyFeatureOutcomeLabelRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, candidate: NewDailyFeatureOutcomeLabel) -> DailyFeatureOutcomeLabel:
        self._ensure_active()
        try:
            self._connection.execute(
                daily_feature_outcome_labels.insert().values(
                    **new_daily_feature_outcome_label_values(candidate)
                )
            )
            stored = self._select(
                daily_feature_outcome_labels.c.daily_feature_outcome_label_id
                == candidate.label.daily_feature_outcome_label_id.value
            )
            if stored is None:
                raise PersistenceMappingError("daily_feature_outcome_label", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_outcome_label", operation="insert"
            ) from None

    def get_by_id(self, label_id: DailyFeatureOutcomeLabelID) -> DailyFeatureOutcomeLabel | None:
        self._ensure_active()
        return self._read(
            daily_feature_outcome_labels.c.daily_feature_outcome_label_id == label_id.value
        )

    def get_by_label_key(self, label_key: str) -> DailyFeatureOutcomeLabel | None:
        self._ensure_active()
        return self._read(daily_feature_outcome_labels.c.label_key == label_key)

    def get_by_source_outcome_and_policy(
        self,
        source_outcome_id: DailyFeatureOutcomeID,
        label_policy_code: str,
        label_policy_version: str,
    ) -> DailyFeatureOutcomeLabel | None:
        self._ensure_active()
        return self._read(
            daily_feature_outcome_labels.c.source_daily_feature_outcome_id
            == source_outcome_id.value,
            daily_feature_outcome_labels.c.label_policy_code == label_policy_code,
            daily_feature_outcome_labels.c.label_policy_version == label_policy_version,
        )

    def list_by_source_scoring_item(
        self, source_item_id: DailyFeatureScoringItemID
    ) -> tuple[DailyFeatureOutcomeLabel, ...]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(daily_feature_outcome_labels)
                    .where(
                        daily_feature_outcome_labels.c.source_daily_feature_scoring_item_id
                        == source_item_id.value
                    )
                    .order_by(
                        daily_feature_outcome_labels.c.generated_at.asc(),
                        daily_feature_outcome_labels.c.label_key.asc(),
                    )
                )
                .mappings()
                .all()
            )
            return tuple(map_daily_feature_outcome_label(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_outcome_label", operation="select"
            ) from None

    def _read(self, *criteria: ColumnElement[bool]) -> DailyFeatureOutcomeLabel | None:
        try:
            return self._select(*criteria)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_outcome_label", operation="select"
            ) from None

    def _select(self, *criteria: ColumnElement[bool]) -> DailyFeatureOutcomeLabel | None:
        row = (
            self._connection.execute(select(daily_feature_outcome_labels).where(*criteria))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_daily_feature_outcome_label(row)
