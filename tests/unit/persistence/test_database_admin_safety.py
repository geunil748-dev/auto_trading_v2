from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine

from auto_trading_v2.adapters.persistence import database_admin
from auto_trading_v2.adapters.persistence.database import (
    ADMIN_URL_ENV,
    DatabaseConfigurationError,
    DatabaseUrl,
    quote_database_identifier,
    validate_database_identifier,
)
from auto_trading_v2.adapters.persistence.database_admin import (
    DEVELOPMENT_DATABASE_NAME,
    DatabaseSafetyError,
    create_development_database,
    drop_test_database,
    validate_development_database_name,
    validate_test_database_name,
)


@pytest.mark.parametrize(
    "database_name",
    ["", "1database", "name-with-dash", "name; DROP DATABASE x", "a]", "a" * 129],
)
def test_invalid_or_injection_like_database_names_are_rejected(database_name: str) -> None:
    with pytest.raises(DatabaseConfigurationError):
        validate_database_identifier(database_name)


def test_development_database_name_is_exact_and_v1_like_names_are_rejected() -> None:
    assert validate_development_database_name("auto_trading_v2") == "auto_trading_v2"
    for name in ("auto_trading", "auto_trading_v1", "auto_trading_v2_copy"):
        with pytest.raises(DatabaseSafetyError):
            validate_development_database_name(name)


def test_test_database_prefix_is_required_for_destructive_cleanup() -> None:
    assert validate_test_database_name("auto_trading_v2_test_abc") == "auto_trading_v2_test_abc"
    for name in ("auto_trading_v2", "auto_trading_v2_test", "other_test_abc"):
        with pytest.raises(DatabaseSafetyError):
            validate_test_database_name(name)


def test_quoted_identifier_is_only_produced_after_strict_validation() -> None:
    assert quote_database_identifier("auto_trading_v2") == "[auto_trading_v2]"
    with pytest.raises(DatabaseConfigurationError):
        quote_database_identifier("auto_trading_v2]; DROP DATABASE master")


def test_database_url_repr_and_errors_never_expose_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "never-print-this-password"
    raw = f"mssql+pyodbc://user:{secret}@example/master?driver=ODBC+Driver+18+for+SQL+Server"
    settings = DatabaseUrl(raw)

    assert secret not in repr(settings)
    assert secret not in str(settings)
    monkeypatch.setenv(ADMIN_URL_ENV, raw)
    loaded = DatabaseUrl.from_environment(ADMIN_URL_ENV)
    assert secret not in repr(loaded)

    with pytest.raises(DatabaseConfigurationError) as caught:
        DatabaseUrl(f"postgresql://user:{secret}@example/database")
    assert secret not in str(caught.value)


def test_only_explicit_v2_environment_names_can_be_read() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseUrl.from_environment("DATABASE_URL")


def test_database_exists_does_not_execute_create_again() -> None:
    engine = MagicMock(spec=Engine)
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one_or_none.return_value = 1
    connection.exec_driver_sql.return_value.mappings.return_value = []

    result = create_development_database(engine)

    assert result.created is False
    assert all(
        "CREATE DATABASE" not in str(call.args[0]) for call in connection.mock_calls if call.args
    )


def test_invalid_test_drop_is_rejected_before_connecting() -> None:
    engine = MagicMock(spec=Engine)

    with pytest.raises(DatabaseSafetyError):
        drop_test_database(engine, DEVELOPMENT_DATABASE_NAME)

    engine.connect.assert_not_called()


def test_no_development_database_drop_api_exists() -> None:
    assert not hasattr(database_admin, "drop_development_database")
