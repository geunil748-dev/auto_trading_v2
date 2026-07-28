import pytest

from auto_trading_v2.adapters.persistence.dotnet import (
    DotNetCommandExecutor,
    DotNetTransaction,
)
from tests.integration.persistence.conftest import (
    TemporaryMssqlDatabase,
    integrated_security_dotnet_connection_factory,
)


@pytest.mark.integration
def test_read_only_connection_and_transaction_rollback_smoke(
    mssql_database: TemporaryMssqlDatabase,
) -> None:
    factory = integrated_security_dotnet_connection_factory(mssql_database)
    executor = DotNetCommandExecutor()
    with factory.opened_connection() as connection:
        assert executor.execute_scalar(connection, "SELECT 1") == 1
        with DotNetTransaction(connection) as transaction:
            assert (
                executor.execute_scalar(
                    connection,
                    "SELECT 1",
                    transaction=transaction.raw_transaction,
                )
                == 1
            )
            transaction.rollback()
