"""Microsoft SQL Server persistence schema and connection boundaries."""

from auto_trading_v2.adapters.persistence.administration import (
    LocalSharedMemoryConnectionInfo,
    MssqlAdministrationEngineFactory,
    MssqlAdministrationErrorCategory,
    MssqlAdministrationSafetyError,
    verify_local_shared_memory_connection,
)
from auto_trading_v2.adapters.persistence.engine import create_mssql_engine
from auto_trading_v2.adapters.persistence.metadata import metadata
from auto_trading_v2.adapters.persistence.tables import BUSINESS_TABLES
from auto_trading_v2.adapters.persistence.unit_of_work import (
    SqlAlchemyUnitOfWork,
    SqlAlchemyUnitOfWorkFactory,
)

__all__ = [
    "BUSINESS_TABLES",
    "LocalSharedMemoryConnectionInfo",
    "MssqlAdministrationEngineFactory",
    "MssqlAdministrationErrorCategory",
    "MssqlAdministrationSafetyError",
    "SqlAlchemyUnitOfWork",
    "SqlAlchemyUnitOfWorkFactory",
    "create_mssql_engine",
    "metadata",
    "verify_local_shared_memory_connection",
]
