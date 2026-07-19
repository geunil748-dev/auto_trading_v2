"""Explicit repository-local dotenv loading and typed settings assembly."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

from auto_trading_v2.config.errors import UnsafeSettingError
from auto_trading_v2.config.models import (
    AppSettings,
    ConfigurationDiagnostics,
    ConfigurationInventory,
    DatabaseSettings,
    KisSettings,
    SecretValue,
    SettingsLoadResult,
    SettingSource,
    TelegramSettings,
)
from auto_trading_v2.config.validation import (
    normalize_choice,
    parse_boolean,
    require_text,
    validate_https_url,
    validate_mssql_url,
)

ENVIRONMENT_KEY = "AUTO_TRADING_V2_ENVIRONMENT"
LOG_LEVEL_KEY = "AUTO_TRADING_V2_LOG_LEVEL"
DB_PROVIDER_KEY = "AUTO_TRADING_V2_DB_PROVIDER"
MSSQL_HOST_KEY = "AUTO_TRADING_V2_MSSQL_HOST"
MSSQL_PORT_KEY = "AUTO_TRADING_V2_MSSQL_PORT"
MSSQL_DATABASE_KEY = "AUTO_TRADING_V2_MSSQL_DATABASE"
MSSQL_USERNAME_KEY = "AUTO_TRADING_V2_MSSQL_USERNAME"
MSSQL_PASSWORD_KEY = "AUTO_TRADING_V2_MSSQL_PASSWORD"
MSSQL_ENCRYPT_KEY = "AUTO_TRADING_V2_MSSQL_ENCRYPT"
MSSQL_TRUST_CERTIFICATE_KEY = "AUTO_TRADING_V2_MSSQL_TRUST_SERVER_CERTIFICATE"
MSSQL_CONNECT_TIMEOUT_KEY = "AUTO_TRADING_V2_MSSQL_CONNECT_TIMEOUT"
MSSQL_ADMIN_URL_KEY = "AUTO_TRADING_V2_MSSQL_ADMIN_URL"
DATABASE_URL_KEY = "AUTO_TRADING_V2_DATABASE_URL"
MSSQL_TEST_ADMIN_URL_KEY = "AUTO_TRADING_V2_TEST_ADMIN_URL"
KIS_ENABLED_KEY = "AUTO_TRADING_V2_KIS_ENABLED"
KIS_ENVIRONMENT_KEY = "AUTO_TRADING_V2_KIS_ENVIRONMENT"
KIS_BASE_URL_KEY = "AUTO_TRADING_V2_KIS_BASE_URL"
KIS_APP_KEY = "AUTO_TRADING_V2_KIS_APP_KEY"
KIS_APP_SECRET_KEY = "AUTO_TRADING_V2_KIS_APP_SECRET"
KIS_ACCOUNT_NUMBER_KEY = "AUTO_TRADING_V2_KIS_ACCOUNT_NUMBER"
KIS_ACCOUNT_PRODUCT_CODE_KEY = "AUTO_TRADING_V2_KIS_ACCOUNT_PRODUCT_CODE"
TELEGRAM_ENABLED_KEY = "AUTO_TRADING_V2_TELEGRAM_ENABLED"
TELEGRAM_BOT_TOKEN_KEY = "AUTO_TRADING_V2_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_KEY = "AUTO_TRADING_V2_TELEGRAM_CHAT_ID"

CANONICAL_KEYS = frozenset(
    {
        ENVIRONMENT_KEY,
        LOG_LEVEL_KEY,
        DB_PROVIDER_KEY,
        MSSQL_HOST_KEY,
        MSSQL_PORT_KEY,
        MSSQL_DATABASE_KEY,
        MSSQL_USERNAME_KEY,
        MSSQL_PASSWORD_KEY,
        MSSQL_ENCRYPT_KEY,
        MSSQL_TRUST_CERTIFICATE_KEY,
        MSSQL_CONNECT_TIMEOUT_KEY,
        MSSQL_ADMIN_URL_KEY,
        DATABASE_URL_KEY,
        MSSQL_TEST_ADMIN_URL_KEY,
        KIS_ENABLED_KEY,
        KIS_ENVIRONMENT_KEY,
        KIS_BASE_URL_KEY,
        KIS_APP_KEY,
        KIS_APP_SECRET_KEY,
        KIS_ACCOUNT_NUMBER_KEY,
        KIS_ACCOUNT_PRODUCT_CODE_KEY,
        TELEGRAM_ENABLED_KEY,
        TELEGRAM_BOT_TOKEN_KEY,
        TELEGRAM_CHAT_ID_KEY,
    }
)

DEFAULTS = {
    ENVIRONMENT_KEY: "development",
    LOG_LEVEL_KEY: "INFO",
    KIS_ENABLED_KEY: "false",
    KIS_ENVIRONMENT_KEY: "paper",
    TELEGRAM_ENABLED_KEY: "false",
}

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def repository_env_file() -> Path:
    """Return the stable repository-root dotenv path without searching parents."""

    return REPOSITORY_ROOT / ".env"


def _select_env_file(env_file: Path | None) -> Path:
    if env_file is None:
        return repository_env_file()
    if env_file.is_absolute():
        return env_file
    return REPOSITORY_ROOT / env_file


def _read_env_file(env_file: Path) -> dict[str, str]:
    if env_file.is_symlink():
        raise UnsafeSettingError("ENV_FILE", "must not be a symbolic link")
    if not env_file.exists():
        return {}
    if not env_file.is_file():
        raise UnsafeSettingError("ENV_FILE", "must be a regular file")
    try:
        parsed = dotenv_values(
            dotenv_path=env_file,
            encoding="utf-8-sig",
            interpolate=False,
            verbose=False,
        )
    except (OSError, UnicodeError):
        raise UnsafeSettingError("ENV_FILE", "could not be read safely") from None
    return {key: value if value is not None else "" for key, value in parsed.items()}


def _inventory_for(env_file: Path, values: Mapping[str, str]) -> ConfigurationInventory:
    keys = frozenset(values)
    configured = len(keys & CANONICAL_KEYS)
    unknown = keys - CANONICAL_KEYS
    legacy = {key for key in unknown if not key.startswith("AUTO_TRADING_V2_")}
    return ConfigurationInventory(
        source_file_present=env_file.exists(),
        canonical_configured_count=configured,
        canonical_missing_count=len(CANONICAL_KEYS) - configured,
        unknown_key_count=len(unknown),
        legacy_key_count=len(legacy),
    )


def inspect_environment_file(env_file: Path | None = None) -> ConfigurationInventory:
    """Inventory key counts without returning names or values."""

    selected = _select_env_file(env_file)
    return _inventory_for(selected, _read_env_file(selected))


class _Resolver:
    def __init__(
        self,
        explicit: Mapping[str, str],
        dotenv: Mapping[str, str],
        process: Mapping[str, str],
    ) -> None:
        self.explicit = explicit
        self.dotenv = dotenv
        self.process = process
        self.sources: dict[str, SettingSource] = {}

    def get(self, key: str) -> str | None:
        if key in self.explicit:
            self.sources[key] = SettingSource.EXPLICIT
            return self.explicit[key]
        if key in self.dotenv:
            self.sources[key] = SettingSource.DOTENV
            return self.dotenv[key]
        if key in self.process:
            self.sources[key] = SettingSource.PROCESS
            return self.process[key]
        if key in DEFAULTS:
            self.sources[key] = SettingSource.DEFAULT
            return DEFAULTS[key]
        self.sources[key] = SettingSource.MISSING
        return None


def _build_database_settings(resolver: _Resolver) -> DatabaseSettings:
    database = validate_mssql_url(
        DATABASE_URL_KEY,
        resolver.get(DATABASE_URL_KEY) or "",
        expected_database="auto_trading_v2",
    )
    admin_raw = resolver.get(MSSQL_ADMIN_URL_KEY)
    test_admin_raw = resolver.get(MSSQL_TEST_ADMIN_URL_KEY)
    admin = (
        validate_mssql_url(MSSQL_ADMIN_URL_KEY, admin_raw, expected_database="master")
        if admin_raw and admin_raw.strip()
        else None
    )
    test_admin = (
        validate_mssql_url(MSSQL_TEST_ADMIN_URL_KEY, test_admin_raw, expected_database="master")
        if test_admin_raw and test_admin_raw.strip()
        else None
    )
    return DatabaseSettings(database_url=database, admin_url=admin, test_admin_url=test_admin)


def _build_kis_settings(resolver: _Resolver) -> KisSettings:
    enabled_raw = require_text(KIS_ENABLED_KEY, resolver.get(KIS_ENABLED_KEY))
    enabled = parse_boolean(KIS_ENABLED_KEY, enabled_raw)
    environment_raw = require_text(KIS_ENVIRONMENT_KEY, resolver.get(KIS_ENVIRONMENT_KEY))
    environment = normalize_choice(KIS_ENVIRONMENT_KEY, environment_raw, {"paper"})
    if not enabled:
        return KisSettings(False, environment, None, None, None, None, None)
    base_url_raw = resolver.get(KIS_BASE_URL_KEY)
    app_key_raw = resolver.get(KIS_APP_KEY)
    app_secret_raw = resolver.get(KIS_APP_SECRET_KEY)
    account_raw = resolver.get(KIS_ACCOUNT_NUMBER_KEY)
    product_raw = resolver.get(KIS_ACCOUNT_PRODUCT_CODE_KEY)
    base_url = validate_https_url(KIS_BASE_URL_KEY, base_url_raw or "")
    return KisSettings(
        enabled=True,
        environment=environment,
        base_url=base_url,
        app_key=SecretValue(require_text(KIS_APP_KEY, app_key_raw)),
        app_secret=SecretValue(require_text(KIS_APP_SECRET_KEY, app_secret_raw)),
        account_number=SecretValue(require_text(KIS_ACCOUNT_NUMBER_KEY, account_raw)),
        account_product_code=SecretValue(require_text(KIS_ACCOUNT_PRODUCT_CODE_KEY, product_raw)),
    )


def _build_telegram_settings(resolver: _Resolver) -> TelegramSettings:
    enabled_raw = require_text(TELEGRAM_ENABLED_KEY, resolver.get(TELEGRAM_ENABLED_KEY))
    enabled = parse_boolean(TELEGRAM_ENABLED_KEY, enabled_raw)
    if not enabled:
        return TelegramSettings(False, None, None)
    token_raw = resolver.get(TELEGRAM_BOT_TOKEN_KEY)
    chat_raw = resolver.get(TELEGRAM_CHAT_ID_KEY)
    return TelegramSettings(
        enabled=True,
        bot_token=SecretValue(require_text(TELEGRAM_BOT_TOKEN_KEY, token_raw)),
        chat_id=SecretValue(require_text(TELEGRAM_CHAT_ID_KEY, chat_raw)),
    )


def load_settings_with_diagnostics(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> SettingsLoadResult:
    """Load explicit overrides, repository dotenv, process values, then defaults."""

    selected = _select_env_file(env_file)
    parsed_dotenv = _read_env_file(selected)
    inventory = _inventory_for(selected, parsed_dotenv)
    dotenv = {key: value for key, value in parsed_dotenv.items() if key in CANONICAL_KEYS}
    process = os.environ if process_environ is None else process_environ
    explicit = {} if environ is None else environ
    resolver = _Resolver(explicit, dotenv, process)
    environment_raw = require_text(ENVIRONMENT_KEY, resolver.get(ENVIRONMENT_KEY))
    environment = normalize_choice(
        ENVIRONMENT_KEY, environment_raw, {"development", "paper", "test"}
    )
    log_level_raw = require_text(LOG_LEVEL_KEY, resolver.get(LOG_LEVEL_KEY))
    log_level = normalize_choice(
        LOG_LEVEL_KEY, log_level_raw, {"CRITICAL", "DEBUG", "ERROR", "INFO", "WARNING"}
    )
    from auto_trading_v2.config.dotnet_database import (
        DOTNET_DATABASE_KEYS,
        load_dotnet_database_settings,
    )

    dotnet_values = {
        key: value for key in DOTNET_DATABASE_KEYS if (value := resolver.get(key)) is not None
    }
    database = load_dotnet_database_settings(
        selected,
        dotnet_values,
        process_environ={},
    )
    settings = AppSettings(
        environment=environment,
        log_level=log_level,
        database=database,
        kis=_build_kis_settings(resolver),
        telegram=_build_telegram_settings(resolver),
    )
    diagnostics = ConfigurationDiagnostics(
        inventory=inventory,
        sources=tuple(sorted(resolver.sources.items())),
    )
    return SettingsLoadResult(settings=settings, diagnostics=diagnostics)


def load_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> AppSettings:
    """Load typed settings only when explicitly called by an application boundary."""

    return load_settings_with_diagnostics(
        env_file,
        environ,
        process_environ=process_environ,
    ).settings
