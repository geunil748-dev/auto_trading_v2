"""DotNet-only runtime persistence composition without provider fallback."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from auto_trading_v2.adapters.persistence.dotnet.connection import DotNetConnectionFactory
from auto_trading_v2.adapters.persistence.dotnet.unit_of_work import DotNetUnitOfWorkFactory
from auto_trading_v2.config import AppSettings, DatabaseProvider, load_settings
from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings
from auto_trading_v2.config.errors import InvalidSettingError
from auto_trading_v2.config.loader import DB_PROVIDER_KEY


def compose_dotnet_persistence(settings: AppSettings) -> DotNetUnitOfWorkFactory:
    """Resolve only the explicit DotNet provider without opening a connection."""

    database = settings.database
    if not isinstance(database, DotNetDatabaseSettings):
        raise InvalidSettingError(DB_PROVIDER_KEY, "must resolve the DotNet provider")
    if database.provider is not DatabaseProvider.DOTNET:
        raise InvalidSettingError(DB_PROVIDER_KEY, "must resolve the DotNet provider")
    return DotNetUnitOfWorkFactory(DotNetConnectionFactory(database))


def load_dotnet_unit_of_work_factory(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> DotNetUnitOfWorkFactory:
    """Load DotNet settings and compose a lazy Unit of Work factory."""

    settings = load_settings(
        env_file,
        environ,
        process_environ=process_environ,
    )
    return compose_dotnet_persistence(settings)


__all__ = ["compose_dotnet_persistence", "load_dotnet_unit_of_work_factory"]
