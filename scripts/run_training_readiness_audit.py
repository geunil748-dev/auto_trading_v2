"""Run a deterministic read-only audit for explicit P4B.2A dataset IDs."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from auto_trading_v2.adapters.clock import SystemClock  # noqa: E402
from auto_trading_v2.adapters.persistence import SqlAlchemyUnitOfWorkFactory  # noqa: E402
from auto_trading_v2.adapters.persistence.database import (  # noqa: E402
    DATABASE_URL_ENV,
    DatabaseConfigurationError,
    DatabaseUrl,
    create_database_engine,
)
from auto_trading_v2.application.contracts.training_readiness import (  # noqa: E402
    RunTrainingReadinessAuditBatchCommand,
)
from auto_trading_v2.application.ports.unit_of_work import UnitOfWorkFactory  # noqa: E402
from auto_trading_v2.application.services.training_readiness import (  # noqa: E402
    TrainingReadinessAuditService,
)
from auto_trading_v2.application.services.training_readiness_report import (  # noqa: E402
    write_training_readiness_reports,
)
from auto_trading_v2.application.training_readiness_errors import (  # noqa: E402
    TrainingReadinessAuditError,
)
from auto_trading_v2.domain.errors import ValidationError  # noqa: E402
from auto_trading_v2.domain.primitives import ProbabilityCalibrationDatasetID  # noqa: E402

DEVELOPMENT_DATABASE_NAME = "auto_trading_v2"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-id",
        action="append",
        required=True,
        dest="dataset_ids",
        help="Explicit ProbabilityCalibrationDataset UUID; may be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "auto_trading_v2_training_readiness_audit",
        help="Repository-external report directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    engine = None
    try:
        identifiers = tuple(
            ProbabilityCalibrationDatasetID.parse(value) for value in args.dataset_ids
        )
        command = RunTrainingReadinessAuditBatchCommand(identifiers)
        settings = DatabaseUrl.from_environment(DATABASE_URL_ENV).require_database(
            DEVELOPMENT_DATABASE_NAME
        )
        engine = create_database_engine(settings)
        factory = cast(UnitOfWorkFactory, SqlAlchemyUnitOfWorkFactory(engine))
        service = TrainingReadinessAuditService(factory, SystemClock())
        result = service.run_batch(command)
        paths = write_training_readiness_reports(result, args.output_dir)
        print(f"audit_dataset_count={len(result.audits)}")
        print(f"report_directory={paths.json_path.parent}")
        print("source_writes=0")
        print("uow_commits=0")
        return 0
    except (DatabaseConfigurationError, ValidationError, ValueError) as exc:
        print(f"training readiness audit blocked: {type(exc).__name__}")
        return 2
    except TrainingReadinessAuditError as exc:
        print(f"training readiness audit blocked: {exc.category}")
        return 3
    except SQLAlchemyError as exc:
        print(f"training readiness audit failed: {type(exc).__name__}")
        return 4
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
