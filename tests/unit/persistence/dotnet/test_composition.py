from pathlib import Path

from auto_trading_v2.adapters.persistence.dotnet.composition import (
    load_dotnet_unit_of_work_factory,
)
from auto_trading_v2.adapters.persistence.dotnet.unit_of_work import DotNetUnitOfWorkFactory
from auto_trading_v2.config.loader import (
    DB_PROVIDER_KEY,
    ENVIRONMENT_KEY,
    MSSQL_CONNECT_TIMEOUT_KEY,
    MSSQL_DATABASE_KEY,
    MSSQL_ENCRYPT_KEY,
    MSSQL_HOST_KEY,
    MSSQL_PASSWORD_KEY,
    MSSQL_PORT_KEY,
    MSSQL_TRUST_CERTIFICATE_KEY,
    MSSQL_USERNAME_KEY,
)


def _environment() -> dict[str, str]:
    return {
        DB_PROVIDER_KEY: "dotnet",
        ENVIRONMENT_KEY: "development",
        MSSQL_HOST_KEY: "localhost",
        MSSQL_PORT_KEY: "1433",
        MSSQL_DATABASE_KEY: "auto_trading_v2",
        MSSQL_USERNAME_KEY: "v2-test-user",
        MSSQL_PASSWORD_KEY: "v2-test-password",
        MSSQL_ENCRYPT_KEY: "false",
        MSSQL_TRUST_CERTIFICATE_KEY: "true",
        MSSQL_CONNECT_TIMEOUT_KEY: "5",
    }


def test_dotnet_only_settings_compose_a_lazy_unit_of_work_factory(tmp_path: Path) -> None:
    factory = load_dotnet_unit_of_work_factory(
        tmp_path / "missing.env",
        process_environ=_environment(),
    )

    assert isinstance(factory, DotNetUnitOfWorkFactory)
    assert factory.connection_factory.settings.provider == "dotnet"
    assert "localhost" not in repr(factory)
    assert "v2-test-password" not in repr(factory)


def test_runtime_composition_has_no_odbc_or_sqlalchemy_online_fallback() -> None:
    source = Path("src/auto_trading_v2/adapters/persistence/dotnet/composition.py").read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "pyodbc",
        "create_mssql_engine",
        "create_database_engine",
        "SqlAlchemyUnitOfWork",
        "create_engine",
        ".connect(",
        "mssql+pyodbc",
    ):
        assert forbidden not in source
