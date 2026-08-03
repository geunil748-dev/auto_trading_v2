"""Sanitized Alpaca historical market-data failure taxonomy."""

from enum import StrEnum


class AlpacaErrorCategory(StrEnum):
    PROVIDER_DISABLED = "ALPACA_PROVIDER_DISABLED"
    CONFIGURATION_MISSING = "ALPACA_CONFIGURATION_MISSING"
    CONFIGURATION_INVALID = "ALPACA_CONFIGURATION_INVALID"
    AUTHENTICATION_REJECTED = "ALPACA_AUTHENTICATION_REJECTED"
    ACCESS_FORBIDDEN = "ALPACA_ACCESS_FORBIDDEN"
    INSTRUMENT_NOT_FOUND = "ALPACA_INSTRUMENT_NOT_FOUND"
    PROVIDER_REJECTED_REQUEST = "ALPACA_PROVIDER_REJECTED_REQUEST"
    RATE_LIMITED = "ALPACA_RATE_LIMITED"
    HTTP_TIMEOUT = "ALPACA_HTTP_TIMEOUT"
    HTTP_TRANSIENT_FAILURE = "ALPACA_HTTP_TRANSIENT_FAILURE"
    HTTP_PERMANENT_FAILURE = "ALPACA_HTTP_PERMANENT_FAILURE"
    RESPONSE_SCHEMA_INVALID = "ALPACA_RESPONSE_SCHEMA_INVALID"
    RESPONSE_VALUE_INVALID = "ALPACA_RESPONSE_VALUE_INVALID"
    PAGINATION_INVALID = "ALPACA_PAGINATION_INVALID"
    NO_DATA = "ALPACA_NO_DATA"
    INGESTION_CONFLICT = "ALPACA_INGESTION_CONFLICT"


_SAFE_PARAMETER_HINTS = frozenset(
    {
        "adjustment",
        "asof",
        "currency",
        "end",
        "feed",
        "limit",
        "page_token",
        "sort",
        "start",
        "symbol",
        "timeframe",
        "unknown",
    }
)


class AlpacaProviderError(RuntimeError):
    """Expose only stable, non-sensitive provider diagnostics."""

    def __init__(
        self,
        category: AlpacaErrorCategory,
        operation: str = "stock_bars",
        *,
        http_status: int | None = None,
        provider_code: int | None = None,
        safe_parameter_hint: str | None = None,
    ) -> None:
        self.category = category
        self.operation = operation if operation == "stock_bars" else "unknown"
        self.http_status = _safe_integer(http_status)
        self.provider_code = _safe_integer(provider_code)
        self.safe_parameter_hint = _safe_hint(safe_parameter_hint)
        super().__init__(self._safe_message())

    def __repr__(self) -> str:
        return f"AlpacaProviderError({self._safe_message()})"

    def _safe_message(self) -> str:
        fields = [f"category={self.category.value}", f"operation={self.operation}"]
        if self.http_status is not None:
            fields.append(f"http_status={self.http_status}")
        if self.provider_code is not None:
            fields.append(f"provider_code={self.provider_code}")
        if self.safe_parameter_hint is not None:
            fields.append(f"safe_parameter_hint={self.safe_parameter_hint}")
        return ", ".join(fields)


def _safe_integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _safe_hint(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in _SAFE_PARAMETER_HINTS else "unknown"
