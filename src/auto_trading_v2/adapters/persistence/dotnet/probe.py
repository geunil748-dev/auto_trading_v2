"""Read-only connection and rollback probes for the DotNet provider."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from auto_trading_v2.adapters.persistence.dotnet.commands import DotNetCommandExecutor
from auto_trading_v2.adapters.persistence.dotnet.connection import DotNetConnectionFactory
from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetErrorCategory,
    DotNetPersistenceError,
    DotNetRuntimeError,
)
from auto_trading_v2.adapters.persistence.dotnet.runtime import load_sqlclient_runtime
from auto_trading_v2.adapters.persistence.dotnet.transaction import DotNetTransaction
from auto_trading_v2.config.dotnet_database import DotNetDatabaseSettings

_CONNECTION_PROPERTY_SQL = """
SELECT
    CONVERT(nvarchar(40), CONNECTIONPROPERTY('net_transport')) AS net_transport,
    CONVERT(nvarchar(40), CONNECTIONPROPERTY('protocol_type')) AS protocol_type,
    CONVERT(nvarchar(40), CONNECTIONPROPERTY('auth_scheme')) AS auth_scheme;
""".strip()


@dataclass(frozen=True, slots=True)
class DotNetProbeResult:
    status: str
    provider: str
    runtime_kind: str
    process_bitness: int
    select_one_status: str
    metadata_status: str
    requested_encrypt: bool
    requested_trust_server_certificate: bool
    net_transport: str | None
    protocol_type: str | None
    auth_scheme: str | None
    elapsed_ms: int
    failure_stage: str
    safe_error_category: str | None
    metadata_safe_error_category: str | None


@dataclass(frozen=True, slots=True)
class DotNetTransactionSmokeResult:
    status: str
    provider: str
    elapsed_ms: int
    failure_stage: str
    safe_error_category: str | None


def _failure_result(
    *,
    started_at: float,
    stage: str,
    category: DotNetErrorCategory,
    runtime_kind: str = "UNKNOWN",
    process_bitness: int = 0,
    requested_encrypt: bool = False,
    requested_trust_server_certificate: bool = False,
) -> DotNetProbeResult:
    return DotNetProbeResult(
        status="FAIL",
        provider="dotnet",
        runtime_kind=runtime_kind,
        process_bitness=process_bitness,
        select_one_status="FAIL",
        metadata_status="NOT_ATTEMPTED",
        requested_encrypt=requested_encrypt,
        requested_trust_server_certificate=requested_trust_server_certificate,
        net_transport=None,
        protocol_type=None,
        auth_scheme=None,
        elapsed_ms=int((perf_counter() - started_at) * 1000),
        failure_stage=stage,
        safe_error_category=category.value,
        metadata_safe_error_category=None,
    )


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def run_read_only_probe(settings: DotNetDatabaseSettings) -> DotNetProbeResult:
    """Open one connection and execute SELECT 1 plus optional connection properties."""

    started_at = perf_counter()
    stage = "RUNTIME"
    runtime_kind = "UNKNOWN"
    process_bitness = 0
    metadata_status = "OPTIONAL_DIAGNOSTIC_UNAVAILABLE"
    metadata_category: str | None = None
    net_transport: str | None = None
    protocol_type: str | None = None
    auth_scheme: str | None = None
    try:
        runtime = load_sqlclient_runtime()
        runtime_kind = runtime.runtime_kind
        process_bitness = runtime.process_bitness
        factory = DotNetConnectionFactory(settings)
        executor = DotNetCommandExecutor()
        stage = "OPEN"
        with factory.opened_connection() as connection:
            stage = "SELECT_1"
            if executor.execute_scalar(connection, "SELECT 1") != 1:
                return _failure_result(
                    started_at=started_at,
                    stage=stage,
                    category=DotNetErrorCategory.UNKNOWN,
                    runtime_kind=runtime_kind,
                    process_bitness=process_bitness,
                    requested_encrypt=settings.encrypt,
                    requested_trust_server_certificate=settings.trust_server_certificate,
                )
            stage = "CONNECTION_METADATA"
            try:
                rows = executor.execute_rows(connection, _CONNECTION_PROPERTY_SQL)
                if rows.rowcount == 1:
                    row = rows[0]
                    net_transport = _optional_text(row["net_transport"])
                    protocol_type = _optional_text(row["protocol_type"])
                    auth_scheme = _optional_text(row["auth_scheme"])
                    metadata_status = "PASS"
            except DotNetPersistenceError as metadata_error:
                metadata_category = metadata_error.category.value
            except Exception:  # noqa: BLE001 - optional diagnostics must remain secret-safe
                metadata_category = DotNetErrorCategory.UNKNOWN.value
        return DotNetProbeResult(
            status="PASS",
            provider="dotnet",
            runtime_kind=runtime_kind,
            process_bitness=process_bitness,
            select_one_status="PASS",
            metadata_status=metadata_status,
            requested_encrypt=settings.encrypt,
            requested_trust_server_certificate=settings.trust_server_certificate,
            net_transport=net_transport,
            protocol_type=protocol_type,
            auth_scheme=auth_scheme,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
            failure_stage="NONE",
            safe_error_category=None,
            metadata_safe_error_category=metadata_category,
        )
    except DotNetRuntimeError:
        return _failure_result(
            started_at=started_at,
            stage=stage,
            category=DotNetErrorCategory.UNKNOWN,
            runtime_kind=runtime_kind,
            process_bitness=process_bitness,
            requested_encrypt=settings.encrypt,
            requested_trust_server_certificate=settings.trust_server_certificate,
        )
    except DotNetPersistenceError as exc:
        return _failure_result(
            started_at=started_at,
            stage=stage,
            category=exc.category,
            runtime_kind=runtime_kind,
            process_bitness=process_bitness,
            requested_encrypt=settings.encrypt,
            requested_trust_server_certificate=settings.trust_server_certificate,
        )
    except Exception:  # noqa: BLE001 - the CLI boundary must never expose raw provider details
        return _failure_result(
            started_at=started_at,
            stage=stage,
            category=DotNetErrorCategory.UNKNOWN,
            runtime_kind=runtime_kind,
            process_bitness=process_bitness,
            requested_encrypt=settings.encrypt,
            requested_trust_server_certificate=settings.trust_server_certificate,
        )


def run_transaction_rollback_smoke(
    settings: DotNetDatabaseSettings,
) -> DotNetTransactionSmokeResult:
    """Begin, SELECT 1, and roll back without DDL or DML."""

    started_at = perf_counter()
    stage = "RUNTIME"
    try:
        load_sqlclient_runtime()
        factory = DotNetConnectionFactory(settings)
        executor = DotNetCommandExecutor()
        stage = "OPEN"
        with factory.opened_connection() as connection:
            stage = "BEGIN"
            with DotNetTransaction(connection) as transaction:
                stage = "SELECT_1"
                scalar = executor.execute_scalar(
                    connection,
                    "SELECT 1",
                    transaction=transaction.raw_transaction,
                )
                if scalar != 1:
                    return DotNetTransactionSmokeResult(
                        "FAIL",
                        "dotnet",
                        int((perf_counter() - started_at) * 1000),
                        stage,
                        DotNetErrorCategory.UNKNOWN.value,
                    )
                stage = "ROLLBACK"
                transaction.rollback()
        return DotNetTransactionSmokeResult(
            "PASS",
            "dotnet",
            int((perf_counter() - started_at) * 1000),
            "NONE",
            None,
        )
    except (DotNetRuntimeError, DotNetPersistenceError) as exc:
        category = (
            exc.category if isinstance(exc, DotNetPersistenceError) else DotNetErrorCategory.UNKNOWN
        )
        return DotNetTransactionSmokeResult(
            "FAIL",
            "dotnet",
            int((perf_counter() - started_at) * 1000),
            stage,
            category.value,
        )
    except Exception:  # noqa: BLE001 - the CLI boundary must never expose raw provider details
        return DotNetTransactionSmokeResult(
            "FAIL",
            "dotnet",
            int((perf_counter() - started_at) * 1000),
            stage,
            DotNetErrorCategory.UNKNOWN.value,
        )
