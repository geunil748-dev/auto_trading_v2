"""SQLAlchemy Core repository for immutable P4B.1 outcome revisions."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import ColumnElement

from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.adapters.persistence.feature_outcome_mapping import (
    map_daily_feature_outcome,
    new_daily_feature_outcome_values,
)
from auto_trading_v2.adapters.persistence.tables import daily_feature_outcomes
from auto_trading_v2.application.contracts.feature_outcomes import NewDailyFeatureOutcome
from auto_trading_v2.application.errors import PersistenceMappingError
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes import DailyFeatureOutcome
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    DailyFeatureScoringItemID,
)
from auto_trading_v2.domain.primitives.time import normalize_utc


def _allow_operation() -> None:
    return None


class SqlAlchemyDailyFeatureOutcomeRepository:
    def __init__(
        self,
        connection: Connection,
        ensure_active: Callable[[], None] = _allow_operation,
        mark_failed: Callable[[], None] = _allow_operation,
    ) -> None:
        self._connection = connection
        self._ensure_active = ensure_active
        self._mark_failed = mark_failed

    def add(self, candidate: NewDailyFeatureOutcome) -> DailyFeatureOutcome:
        self._ensure_active()
        try:
            self._connection.execute(
                daily_feature_outcomes.insert().values(
                    **new_daily_feature_outcome_values(candidate)
                )
            )
            stored = self._select(
                daily_feature_outcomes.c.daily_feature_outcome_id
                == candidate.outcome.daily_feature_outcome_id.value
            )
            if stored is None:
                raise PersistenceMappingError("daily_feature_outcome", "insert")
            return stored
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_outcome", operation="insert"
            ) from None

    def get_by_id(self, outcome_id: DailyFeatureOutcomeID) -> DailyFeatureOutcome | None:
        self._ensure_active()
        return self._read(daily_feature_outcomes.c.daily_feature_outcome_id == outcome_id.value)

    def get_by_outcome_key(self, outcome_key: str) -> DailyFeatureOutcome | None:
        self._ensure_active()
        return self._read(daily_feature_outcomes.c.outcome_key == outcome_key)

    def list_by_source_scoring_item(
        self, source_item_id: DailyFeatureScoringItemID
    ) -> tuple[DailyFeatureOutcome, ...]:
        self._ensure_active()
        try:
            rows = (
                self._connection.execute(
                    select(daily_feature_outcomes)
                    .where(
                        daily_feature_outcomes.c.source_daily_feature_scoring_item_id
                        == source_item_id.value
                    )
                    .order_by(
                        daily_feature_outcomes.c.latest_input_available_at.asc(),
                        daily_feature_outcomes.c.outcome_key.asc(),
                    )
                )
                .mappings()
                .all()
            )
            return tuple(map_daily_feature_outcome(row) for row in rows)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_outcome", operation="select"
            ) from None

    def get_latest_available_by_source_scoring_item(
        self,
        source_item_id: DailyFeatureScoringItemID,
        as_of: datetime,
    ) -> DailyFeatureOutcome | None:
        self._ensure_active()
        try:
            cutoff = normalize_utc(as_of)
        except ValidationError:
            raise ValueError("as_of must be timezone-aware") from None
        try:
            row = (
                self._connection.execute(
                    select(daily_feature_outcomes)
                    .where(
                        daily_feature_outcomes.c.source_daily_feature_scoring_item_id
                        == source_item_id.value,
                        daily_feature_outcomes.c.latest_input_available_at <= cutoff,
                    )
                    .order_by(
                        daily_feature_outcomes.c.latest_input_available_at.desc(),
                        daily_feature_outcomes.c.outcome_key.desc(),
                    )
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else map_daily_feature_outcome(row)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_outcome", operation="select"
            ) from None

    def _read(self, *criteria: ColumnElement[bool]) -> DailyFeatureOutcome | None:
        try:
            return self._select(*criteria)
        except PersistenceMappingError:
            self._mark_failed()
            raise
        except SQLAlchemyError as exc:
            self._mark_failed()
            raise translate_persistence_error(
                exc, entity="daily_feature_outcome", operation="select"
            ) from None

    def _select(self, *criteria: ColumnElement[bool]) -> DailyFeatureOutcome | None:
        row = (
            self._connection.execute(select(daily_feature_outcomes).where(*criteria))
            .mappings()
            .one_or_none()
        )
        return None if row is None else map_daily_feature_outcome(row)
