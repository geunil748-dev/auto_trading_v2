"""Secret-safe System.Data.SqlClient connection builder and factory."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import Any, cast

from auto_trading_v2.adapters.persistence.dotnet.errors import safe_persistence_error
from auto_trading_v2.adapters.persistence.dotnet.runtime import (
    DotNetBindings,
    get_sqlclient_bindings,
)
from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings


@dataclass(slots=True, repr=False)
class DotNetConnectionFactory:
    """Create fresh SqlConnections without exposing their connection string."""

    settings: DotNetDatabaseSettings = field(repr=False)
    bindings_provider: Callable[[], DotNetBindings] = field(
        default=get_sqlclient_bindings,
        repr=False,
    )

    def _new_builder(self, bindings: DotNetBindings) -> Any:
        builder: Any = bindings.sql_connection_string_builder()
        builder.DataSource = self.settings.data_source
        builder.InitialCatalog = self.settings.database
        builder.UserID = self.settings.username.reveal()
        builder.Password = self.settings.password.reveal()
        builder.IntegratedSecurity = False
        builder.Encrypt = self.settings.encrypt
        builder.TrustServerCertificate = self.settings.trust_server_certificate
        builder.ConnectTimeout = self.settings.connect_timeout
        builder.PersistSecurityInfo = False
        builder.ApplicationName = "auto_trading_v2"
        builder.MultipleActiveResultSets = False
        return builder

    def create_connection(self) -> object:
        """Return a fresh unopened SqlConnection."""

        bindings = self.bindings_provider()
        builder = self._new_builder(bindings)
        connection_type: Any = bindings.sql_connection
        return cast(object, connection_type(builder.ConnectionString))

    def open_connection(self) -> object:
        """Open a fresh connection or raise a sanitized persistence error."""

        connection = self.create_connection()
        dynamic: Any = connection
        try:
            dynamic.Open()
        except Exception as exc:
            with suppress(Exception):
                dynamic.Dispose()
            raise safe_persistence_error(exc, operation="open") from None
        return connection

    @contextmanager
    def opened_connection(self) -> Iterator[object]:
        """Open, close, and dispose a connection without leaking close messages."""

        connection = self.open_connection()
        dynamic: Any = connection
        try:
            yield connection
        except BaseException:
            with suppress(Exception):
                dynamic.Close()
            with suppress(Exception):
                dynamic.Dispose()
            raise
        else:
            close_error: Exception | None = None
            try:
                dynamic.Close()
            except Exception as exc:
                close_error = exc
            finally:
                try:
                    dynamic.Dispose()
                except Exception as exc:
                    if close_error is None:
                        close_error = exc
            if close_error is not None:
                raise safe_persistence_error(close_error, operation="close") from None
