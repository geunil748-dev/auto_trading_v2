from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine

from auto_trading_v2.application.contracts.calibration_datasets import (
    CalibrationDatasetSourceRecord,
    NewProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.calibration_datasets import (
    ProbabilityCalibrationDatasetWithItems,
)
from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    SOURCE_PROVIDER_CODE,
    ForwardReturn,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.feature_scoring import (
    RelativeScore,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus, TradingDayHorizon
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabel,
    PositiveForwardCloseLabel,
)
from auto_trading_v2.domain.primitives import (
    DailyFeatureOutcomeID,
    ProbabilityCalibrationDatasetID,
    ProbabilityCalibrationDatasetItemID,
    SessionDate,
    Symbol,
)
from tests.integration.training_readiness.synthetic_fixture_support import (
    TABLE_ORDER as _TABLE_ORDER,
)
from tests.integration.training_readiness.synthetic_fixture_support import (
    aggregate_dataset as _aggregate,
)
from tests.integration.training_readiness.synthetic_fixture_support import (
    append_universe_and_runs as _append_universe_and_runs,
)
from tests.integration.training_readiness.synthetic_fixture_support import (
    item_ids as _item_ids,
)
from tests.integration.training_readiness.synthetic_fixture_support import (
    label as _label,
)
from tests.integration.training_readiness.synthetic_fixture_support import (
    run_ids as _run_ids,
)
from tests.integration.training_readiness.synthetic_rows import (
    append_ready_rows as _append_ready_rows,
)
from tests.integration.training_readiness.synthetic_rows import (
    pipeline_item as _pipeline_item,
)
from tests.integration.training_readiness.synthetic_rows import (
    scoring_item as _scoring_item,
)
from tests.integration.training_readiness.synthetic_rows import (
    snapshot as _snapshot,
)
from tests.unit.p4b2a_helpers import dataset_identity

SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "META")
HORIZON = TradingDayHorizon(1)
GENERATED_AT = datetime(2026, 8, 3, 1, tzinfo=UTC)
EMPTY_AS_OF = datetime(2024, 1, 1, tzinfo=UTC)
REPLAY_AS_OF = datetime(2025, 3, 2, 23, tzinfo=UTC)
FULL_AS_OF = datetime(2025, 5, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SyntheticDatasets:
    ready: ProbabilityCalibrationDatasetWithItems
    prospective_insufficient: ProbabilityCalibrationDatasetWithItems
    empty: ProbabilityCalibrationDatasetWithItems


@dataclass
class DatasetIDs:
    next_value: int

    def new(self) -> ProbabilityCalibrationDatasetID:
        self.next_value += 1
        return ProbabilityCalibrationDatasetID(UUID(int=self.next_value))


@dataclass
class ItemIDs:
    next_value: int

    def new(self) -> ProbabilityCalibrationDatasetItemID:
        self.next_value += 1
        return ProbabilityCalibrationDatasetItemID(UUID(int=self.next_value))


def seed_synthetic_readiness_data(engine: Engine) -> SyntheticDatasets:
    rows = {name: [] for name in _TABLE_ORDER}
    sources: list[CalibrationDatasetSourceRecord] = []
    labels: dict[DailyFeatureOutcomeID, DailyFeatureOutcomeLabel] = {}
    start = date(2025, 1, 2)
    for run_index in range(80):
        session = start + timedelta(days=run_index)
        mode = (
            OutcomeObservationMode.RETROSPECTIVE_REPLAY
            if run_index < 60
            else OutcomeObservationMode.PROSPECTIVE
        )
        _append_run(rows, sources, labels, run_index, session, mode)
    _append_degraded_run(rows, 80, start + timedelta(days=80))
    _append_policy_mismatch_run(rows, 81, start + timedelta(days=81))
    with engine.begin() as connection:
        for name, table in _TABLE_ORDER.items():
            values = rows[name]
            if values:
                connection.execute(table.insert(), values)
    ready = _aggregate(dataset_identity(as_of=FULL_AS_OF), tuple(sources), labels, 900_000)
    replay_sources = tuple(
        source
        for source in sources
        if source.observation_mode is OutcomeObservationMode.RETROSPECTIVE_REPLAY
    )
    prospective_insufficient = _aggregate(
        dataset_identity(as_of=REPLAY_AS_OF), replay_sources, labels, 910_000
    )
    empty = _aggregate(dataset_identity(as_of=EMPTY_AS_OF), (), labels, 920_000)
    return SyntheticDatasets(ready, prospective_insufficient, empty)


def persist_datasets(factory: object, datasets: SyntheticDatasets) -> None:
    for aggregate in (datasets.ready, datasets.prospective_insufficient, datasets.empty):
        with factory() as unit_of_work:  # type: ignore[operator]
            stored = unit_of_work.probability_calibration_datasets.add_dataset_with_items(
                NewProbabilityCalibrationDatasetWithItems(aggregate)
            )
            assert stored.dataset.content_digest == aggregate.dataset.content_digest
            unit_of_work.commit()


def _append_run(
    rows: dict[str, list[dict[str, object]]],
    sources: list[CalibrationDatasetSourceRecord],
    labels: dict[DailyFeatureOutcomeID, DailyFeatureOutcomeLabel],
    run_index: int,
    session: date,
    mode: OutcomeObservationMode,
) -> None:
    ids = _run_ids(run_index)
    run_time = datetime.combine(session, time(21), UTC)
    _append_universe_and_runs(rows, ids, run_index, session, run_time, 5, 5, 0)
    for ordinal, symbol_text in enumerate(SYMBOLS, 1):
        index = run_index * 5 + ordinal
        positive = index % 2 == 0
        item_ids = _item_ids(index)
        outcome_digest = _digest(f"outcome-content-{index}")
        path_digest = _digest(f"outcome-path-{index}")
        outcome_key = f"daily-feature-outcome:v1:{_digest(f'outcome-key-{index}')}"
        source_date = SessionDate(session)
        terminal_date = SessionDate(session + timedelta(days=3))
        symbol = Symbol(symbol_text)
        score = RelativeScore(Decimal(ordinal * 10))
        label_value = (
            PositiveForwardCloseLabel.POSITIVE
            if positive
            else PositiveForwardCloseLabel.NOT_POSITIVE
        )
        _append_ready_rows(
            rows,
            ids,
            item_ids,
            ordinal,
            symbol_text,
            session,
            run_time,
            mode,
            positive,
            outcome_key,
            outcome_digest,
            path_digest,
        )
        source = CalibrationDatasetSourceRecord(
            ids[1],
            item_ids[2],
            ids[0],
            item_ids[1],
            item_ids[0],
            item_ids[3],
            outcome_key,
            outcome_digest,
            path_digest,
            symbol,
            "XNGS",
            HORIZON,
            source_date,
            terminal_date,
            run_time + timedelta(minutes=4),
            run_time + timedelta(minutes=4),
            run_time + timedelta(minutes=5),
            run_time + timedelta(minutes=5),
            mode,
            FeatureQualityStatus.READY,
            score,
            ordinal,
            ForwardReturn(Decimal("0.01") if positive else Decimal("-0.01")),
            SOURCE_PROVIDER_CODE,
            CALENDAR_CODE,
            CALENDAR_VERSION,
        )
        sources.append(source)
        labels[item_ids[3]] = _label(source, item_ids[4], label_value, run_time)


def _append_degraded_run(
    rows: dict[str, list[dict[str, object]]], run_index: int, session: date
) -> None:
    ids = _run_ids(run_index)
    item_ids = _item_ids(1000)
    run_time = datetime.combine(session, time(21), UTC)
    _append_universe_and_runs(rows, ids, run_index, session, run_time, 1, 0, 1)
    rows["feature_snapshots"].append(
        _snapshot(item_ids[0], "TSLA", session, run_time, "DEGRADED", '["VOLUME_DATA_INCOMPLETE"]')
    )
    rows["pipeline_items"].append(
        _pipeline_item(item_ids[1], ids[0], item_ids[0], 1, "TSLA", session, run_time, "DEGRADED")
    )
    rows["scoring_items"].append(
        _scoring_item(item_ids[2], ids[1], item_ids[1], item_ids[0], 1, "TSLA", run_time, True)
    )


def _append_policy_mismatch_run(
    rows: dict[str, list[dict[str, object]]], run_index: int, session: date
) -> None:
    ids = _run_ids(run_index)
    item_ids = _item_ids(1001)
    run_time = datetime.combine(session, time(21), UTC)
    _append_universe_and_runs(rows, ids, run_index, session, run_time, 1, 1, 0)
    rows["scoring_runs"][-1]["scoring_policy_version"] = "mismatch-v1"
    rows["feature_snapshots"].append(
        _snapshot(item_ids[0], "ORCL", session, run_time, "READY", "[]")
    )
    rows["pipeline_items"].append(
        _pipeline_item(item_ids[1], ids[0], item_ids[0], 1, "ORCL", session, run_time, "READY")
    )
    rows["scoring_items"].append(
        _scoring_item(item_ids[2], ids[1], item_ids[1], item_ids[0], 1, "ORCL", run_time, False)
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
