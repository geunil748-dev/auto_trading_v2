"""Deterministic secret-safe report rendering and atomic output."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from auto_trading_v2.domain.training_readiness import TrainingReadinessAuditBatchResult


@dataclass(frozen=True, slots=True)
class TrainingReadinessReportPaths:
    json_path: Path
    markdown_path: Path
    sha256_path: Path


def render_training_readiness_json(result: TrainingReadinessAuditBatchResult) -> str:
    return json.dumps(_primitive(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_training_readiness_markdown(result: TrainingReadinessAuditBatchResult) -> str:
    lines = [
        "# Training Readiness Audit",
        "",
        f"Generated at (UTC): `{_utc(result.audit_generated_at)}`",
        "",
        "This report is read-only. It does not create a model, probability artifact, "
        "Recommendation, market data, order, outcome, label, or dataset.",
        "",
    ]
    for audit in result.audits:
        identity = audit.dataset_identity
        included = audit.included_dataset
        upstream = audit.upstream_quality
        decision = audit.data_quality_decision_evidence
        price_only_eligibility = (
            decision.price_only_eligibility.percentage
            or decision.price_only_eligibility.status.value
        )
        lines.extend(
            [
                f"## Dataset `{identity.probability_calibration_dataset_id}`",
                "",
                f"- Horizon: {identity.horizon_trading_days} trading day(s)",
                f"- Status: {identity.status}",
                f"- Content digest: `{identity.content_digest}`",
                f"- Dataset as-of: `{_utc(identity.dataset_as_of)}`",
                f"- Included items: {included.total_item_count}",
                f"- Source sessions: {included.unique_source_session_count}",
                f"- Symbol/listings: {included.unique_symbol_listing_count}",
                f"- Replay / prospective: {included.retrospective_replay_item_count} / "
                f"{included.prospective_item_count}",
                f"- Positive / not-positive: {included.positive_count} / "
                f"{included.not_positive_count}",
                f"- Upstream scoring items: {upstream.source_scoring_item_count}",
                f"- READY / DEGRADED scoring: {upstream.scored_ready_count} / "
                f"{upstream.scored_degraded_count}",
                f"- Volume incomplete: {upstream.volume_data_incomplete_count}",
                f"- Price features complete: {upstream.price_feature_complete_count}",
                f"- Volume-only degraded: {upstream.volume_only_degraded_count}",
                f"- Price-only v2 eligible / ineligible: "
                f"{upstream.price_only_v2_eligible_count} / "
                f"{upstream.price_only_v2_ineligible_count}",
                f"- Legacy readiness: {audit.legacy_calibration_readiness.status.value}",
                f"- MVP readiness: {audit.mvp_trade_model_readiness.status.value}",
                f"- Price-only eligibility: {price_only_eligibility}",
                f"- Price-only source sessions before / after: "
                f"{decision.price_only_source_session_count_before_eligibility} / "
                f"{decision.price_only_source_session_count_after_eligibility}",
                f"- Price-only symbols before / after: "
                f"{decision.price_only_symbol_count_before_eligibility} / "
                f"{decision.price_only_symbol_count_after_eligibility}",
                "",
                "### Exclusion reasons",
                "",
            ]
        )
        lines.extend(f"- {fact.code}: {fact.count}" for fact in upstream.exclusion_reason_counts)
        lines.extend(["", "### Price-only v2 ineligibility reasons", ""])
        lines.extend(
            f"- {fact.code}: {fact.count}"
            for fact in upstream.price_only_v2_ineligibility_reason_counts
        )
        lines.extend(["", "### MVP blockers", ""])
        lines.extend(f"- {blocker}" for blocker in audit.mvp_trade_model_readiness.blockers)
        lines.extend(["", "### Not derivable", ""])
        lines.extend(f"- {field}" for field in audit.not_derivable_fields)
        lines.extend(["", audit.legacy_calibration_readiness.limitation, ""])
    lines.extend(["## Conclusion", ""])
    lines.extend(f"- {audit.conclusion}" for audit in result.audits)
    return "\n".join(lines) + "\n"


def write_training_readiness_reports(
    result: TrainingReadinessAuditBatchResult,
    output_dir: Path,
) -> TrainingReadinessReportPaths:
    directory = output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "training_readiness_audit.json"
    markdown_path = directory / "training_readiness_audit.md"
    sha_path = directory / "training_readiness_audit.sha256"
    json_text = render_training_readiness_json(result)
    markdown_text = render_training_readiness_markdown(result)
    digest = hashlib.sha256(json_text.encode("utf-8")).hexdigest()
    _atomic_write(json_path, json_text)
    _atomic_write(markdown_path, markdown_text)
    _atomic_write(sha_path, f"{digest}  {json_path.name}\n")
    return TrainingReadinessReportPaths(json_path, markdown_path, sha_path)


def _primitive(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _utc(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
