"""Explicit, secret-safe application configuration boundary."""

from auto_trading_v2.config.dotnet_database import (
    DOTNET_DATABASE_KEYS,
    DotNetDatabaseInventory,
    DotNetDatabaseSettings,
    inspect_dotnet_database_settings,
    load_dotnet_database_settings,
)
from auto_trading_v2.config.errors import (
    ConfigurationError,
    InvalidSettingError,
    MissingSettingError,
    UnsafeSettingError,
)
from auto_trading_v2.config.loader import (
    CANONICAL_KEYS,
    inspect_environment_file,
    load_settings,
    load_settings_with_diagnostics,
    repository_env_file,
)
from auto_trading_v2.config.models import (
    AppSettings,
    ConfigurationDiagnostics,
    ConfigurationInventory,
    DatabaseProvider,
    DatabaseSettings,
    KisSettings,
    SecretValue,
    SettingsLoadResult,
    SettingSource,
    TelegramSettings,
)

__all__ = [
    "CANONICAL_KEYS",
    "AppSettings",
    "ConfigurationDiagnostics",
    "ConfigurationError",
    "ConfigurationInventory",
    "DatabaseSettings",
    "DatabaseProvider",
    "DOTNET_DATABASE_KEYS",
    "DotNetDatabaseInventory",
    "DotNetDatabaseSettings",
    "InvalidSettingError",
    "KisSettings",
    "MissingSettingError",
    "SecretValue",
    "SettingSource",
    "SettingsLoadResult",
    "TelegramSettings",
    "UnsafeSettingError",
    "inspect_environment_file",
    "inspect_dotnet_database_settings",
    "load_dotnet_database_settings",
    "load_settings",
    "load_settings_with_diagnostics",
    "repository_env_file",
]
