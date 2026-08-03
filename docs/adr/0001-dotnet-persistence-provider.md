# ADR 0001: DotNet persistence provider

## Status

Accepted for V2 local development and local paper trading.

## Decision

V2 runtime persistence uses `System.Data.SqlClient` through `pythonnet` with an explicitly
selected `.NET Framework` runtime. `AUTO_TRADING_V2_DB_PROVIDER` must be `dotnet`. Runtime
startup fails fast when pythonnet, the CLR, `System.Data`, configuration, authentication, or
connectivity is unavailable. There is no ODBC fallback.

The initial connection policy is local-only SQL authentication with `Encrypt=False`,
`TrustServerCertificate=True`, a five-second timeout, an exact `auto_trading_v2` database name,
and a dedicated least-privilege V2 login. Endpoint and credential values are never logged.

## Boundaries

The V2 runtime composition now provides configuration, lazy runtime loading, connection and
transaction lifecycle, parameterized commands, result conversion, safe error classification,
read-only probes, all nine persistence repositories, and the application Unit of Work contract.
One `DotNetUnitOfWork` owns exactly one `SqlConnection` and one `SqlTransaction`; repositories
receive that same pair and never open, close, commit, or roll back either resource.

Existing repository SQLAlchemy Core statements and row mappings are retained as provider-neutral
contract implementations. A DotNet adapter compiles those statements with the MSSQL dialect and
executes the resulting named, explicitly typed parameters through `System.Data.SqlClient`.
SQLAlchemy does not create an Engine or online Connection in this runtime path.

SQLAlchemy metadata and Alembic revisions remain available for DDL compilation and migration
administration. Existing SQLAlchemy repositories, Unit of Work, pyodbc dependency, and legacy URL
settings remain only for compatibility and administrative follow-up work; DotNet runtime
composition does not reference them. This change does not alter the canonical schema or execute
migrations.

## Consequences

The known ODBC pre-login TLS failure remains an unused-provider defect and is not a V2 runtime
blocker. A DotNet failure fails fast with a sanitized category and never falls back to ODBC.
Online Alembic execution is outside the official runtime path and remains a separate follow-up.
