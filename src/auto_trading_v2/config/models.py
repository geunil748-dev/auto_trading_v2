"""Immutable typed settings and secret value protection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings


class SecretValue:
    """Hold a non-empty secret and reveal it only through an explicit call."""

    __slots__ = ("__value",)
    __value: str

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("SecretValue requires a non-empty value")
        object.__setattr__(self, "_SecretValue__value", value)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("SecretValue is immutable")

    def __copy__(self) -> SecretValue:
        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> SecretValue:
        return self

    def reveal(self) -> str:
        """Return the protected value at an authorized integration boundary."""

        return self.__value

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Validated V2 MSSQL connection settings without opening a connection."""

    database_url: SecretValue
    admin_url: SecretValue | None
    test_admin_url: SecretValue | None


class DatabaseProvider(StrEnum):
    """Explicit runtime persistence provider."""

    DOTNET = "dotnet"


@dataclass(frozen=True, slots=True)
class KisSettings:
    """KIS paper configuration without HTTP client or token behavior."""

    enabled: bool
    environment: str
    base_url: str | None
    app_key: SecretValue | None
    app_secret: SecretValue | None
    account_number: SecretValue | None
    account_product_code: SecretValue | None


@dataclass(frozen=True, slots=True)
class TelegramSettings:
    """Telegram configuration without client or message delivery behavior."""

    enabled: bool
    bot_token: SecretValue | None
    chat_id: SecretValue | None


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Application configuration assembled at an explicit boundary."""

    environment: str
    log_level: str
    database: DotNetDatabaseSettings
    kis: KisSettings
    telegram: TelegramSettings


class SettingSource(StrEnum):
    """Safe source labels for diagnostics."""

    EXPLICIT = "explicit"
    DOTENV = "dotenv"
    PROCESS = "process"
    DEFAULT = "default"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class ConfigurationInventory:
    """Counts only; unknown names and all values are intentionally discarded."""

    source_file_present: bool
    canonical_configured_count: int
    canonical_missing_count: int
    unknown_key_count: int
    legacy_key_count: int


@dataclass(frozen=True, slots=True)
class ConfigurationDiagnostics:
    """Value-free source metadata for a successful settings load."""

    inventory: ConfigurationInventory
    sources: tuple[tuple[str, SettingSource], ...]

    def source_for(self, key: str) -> SettingSource:
        """Return the recorded source for one canonical key."""

        return dict(self.sources).get(key, SettingSource.MISSING)


@dataclass(frozen=True, slots=True)
class SettingsLoadResult:
    """Typed settings paired with diagnostics that contain no raw values."""

    settings: AppSettings
    diagnostics: ConfigurationDiagnostics
