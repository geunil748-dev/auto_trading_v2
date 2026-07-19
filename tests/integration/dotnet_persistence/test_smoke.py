import pytest

from auto_trading_v2.adapters.persistence.dotnet import (
    run_read_only_probe,
    run_transaction_rollback_smoke,
)
from auto_trading_v2.config.dotnet_database import (
    inspect_dotnet_database_settings,
    load_dotnet_database_settings,
)


@pytest.mark.integration
def test_read_only_connection_and_transaction_rollback_smoke() -> None:
    inventory = inspect_dotnet_database_settings()
    if inventory.missing_count:
        pytest.skip("DotNet persistence integration environment is not configured")

    settings = load_dotnet_database_settings()

    probe = run_read_only_probe(settings)
    transaction = run_transaction_rollback_smoke(settings)

    assert probe.status == "PASS"
    assert transaction.status == "PASS"
