"""Emit a secret-safe JSON result for the optional read-only DotNet probe."""

from __future__ import annotations

import json
from dataclasses import asdict

from auto_trading_v2.adapters.persistence.dotnet import (
    run_read_only_probe,
    run_transaction_rollback_smoke,
)
from auto_trading_v2.config import ConfigurationError
from auto_trading_v2.config.dotnet_database import (
    inspect_dotnet_database_settings,
    load_dotnet_database_settings,
)


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


def main() -> int:
    inventory = inspect_dotnet_database_settings()
    if inventory.missing_count:
        _print(
            {
                "status": "BLOCKED",
                "classification": "DOTNET_ENVIRONMENT_NOT_CONFIGURED",
                "provider": "dotnet",
                "resolved_provider": "dotnet",
                "missing_key_count": inventory.missing_count,
                "connection_attempted": False,
            }
        )
        return 2
    try:
        settings = load_dotnet_database_settings()
    except ConfigurationError:
        _print(
            {
                "status": "BLOCKED",
                "classification": "DOTNET_CONFIGURATION_INVALID",
                "provider": "dotnet",
                "resolved_provider": "dotnet",
                "connection_attempted": False,
            }
        )
        return 2

    probe = run_read_only_probe(settings)
    if probe.status != "PASS":
        _print(
            {
                **asdict(probe),
                "status": "BLOCKED",
                "classification": "DOTNET_READ_ONLY_PROBE_FAILED",
                "resolved_provider": "dotnet",
            }
        )
        return 1
    transaction = run_transaction_rollback_smoke(settings)
    status = "PASS" if transaction.status == "PASS" else "BLOCKED"
    classification = (
        "DOTNET_PERSISTENCE_FOUNDATION_VALIDATED"
        if status == "PASS"
        else "DOTNET_TRANSACTION_ROLLBACK_SMOKE_FAILED"
    )
    _print(
        {
            **asdict(probe),
            "status": status,
            "classification": classification,
            "resolved_provider": "dotnet",
            "transaction_status": transaction.status,
            "transaction_elapsed_ms": transaction.elapsed_ms,
            "transaction_failure_stage": transaction.failure_stage,
            "transaction_safe_error_category": transaction.safe_error_category,
        }
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
