import hashlib
from pathlib import Path

from auto_trading_v2.application.contracts.training_readiness import (
    RunTrainingReadinessAuditBatchCommand,
)
from auto_trading_v2.application.services.training_readiness_report import (
    render_training_readiness_json,
    render_training_readiness_markdown,
    write_training_readiness_reports,
)
from tests.unit.training_readiness_helpers import service_context


def test_reports_are_deterministic_atomic_utf8_and_secret_safe(tmp_path: Path) -> None:
    service, _, value = service_context()
    result = service.run_batch(
        RunTrainingReadinessAuditBatchCommand((value.dataset.probability_calibration_dataset_id,))
    )

    first_json = render_training_readiness_json(result)
    second_json = render_training_readiness_json(result)
    markdown = render_training_readiness_markdown(result)
    paths = write_training_readiness_reports(result, tmp_path)
    write_training_readiness_reports(result, tmp_path)
    raw = paths.json_path.read_bytes()
    expected_hash = hashlib.sha256(raw).hexdigest()

    assert first_json == second_json == raw.decode("utf-8")
    assert markdown == paths.markdown_path.read_text(encoding="utf-8")
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert paths.sha256_path.read_text(encoding="utf-8") == (
        f"{expected_hash}  training_readiness_audit.json\n"
    )
    forbidden = ("password=", "apikey=", "authorization:", "mssql+pyodbc://")
    assert all(value not in first_json.casefold() for value in forbidden)
    assert not (tmp_path / ".training_readiness_audit.json.tmp").exists()
