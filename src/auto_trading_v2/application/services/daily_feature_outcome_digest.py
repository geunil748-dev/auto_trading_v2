"""Canonical digest payload for a not-yet-persisted P4B.1 outcome."""

from typing import Any

from auto_trading_v2.domain.primitives.time import UtcTimestamp


def outcome_content_payload(values: dict[str, Any]) -> dict[str, object]:
    provenance = values["future_bar_provenance"]
    return {
        "calendar_code": values["calendar_code"].value,
        "calendar_version": values["calendar_version"].value,
        "feature_snapshot_id": values["feature_snapshot_id"].serialize(),
        "forward_close_return": values["forward_close_return"].serialize(),
        "future_bar_count": values["future_bar_count"],
        "future_bar_provenance": [entry.as_json() for entry in provenance],
        "horizon_trading_days": values["horizon"].value,
        "latest_input_available_at": UtcTimestamp(values["latest_input_available_at"]).serialize(),
        "maximum_adverse_excursion_rate": values["maximum_adverse_excursion_rate"].serialize(),
        "maximum_favorable_excursion_rate": values["maximum_favorable_excursion_rate"].serialize(),
        "mic_code": values["mic_code"],
        "observation_mode": values["observation_mode"].value,
        "outcome_policy_code": values["outcome_policy_code"].value,
        "outcome_policy_version": values["outcome_policy_version"].value,
        "provider_code": values["provider_code"],
        "reference_close": format(values["reference_close"], ".18f"),
        "source_daily_feature_pipeline_item_id": values[
            "source_daily_feature_pipeline_item_id"
        ].serialize(),
        "source_daily_feature_pipeline_run_id": values[
            "source_daily_feature_pipeline_run_id"
        ].serialize(),
        "source_daily_feature_scoring_item_id": values[
            "source_daily_feature_scoring_item_id"
        ].serialize(),
        "source_daily_feature_scoring_run_id": values[
            "source_daily_feature_scoring_run_id"
        ].serialize(),
        "source_session_date": values["source_session_date"].serialize(),
        "symbol": values["symbol"].serialize(),
        "terminal_close": format(values["terminal_close"], ".18f"),
        "terminal_session_date": values["terminal_session_date"].serialize(),
    }
