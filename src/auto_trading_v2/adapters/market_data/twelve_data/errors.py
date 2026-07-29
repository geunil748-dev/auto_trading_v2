"""Sanitized Twelve Data failure taxonomy."""

from enum import StrEnum


class TwelveDataErrorCategory(StrEnum):
    PROVIDER_DISABLED = "TWELVE_DATA_PROVIDER_DISABLED"
    CONFIGURATION_MISSING = "TWELVE_DATA_CONFIGURATION_MISSING"
    CONFIGURATION_INVALID = "TWELVE_DATA_CONFIGURATION_INVALID"
    MINUTE_CREDIT_LIMIT = "TWELVE_DATA_MINUTE_CREDIT_LIMIT"
    DAILY_CREDIT_BUDGET_EXHAUSTED = "TWELVE_DATA_DAILY_CREDIT_BUDGET_EXHAUSTED"
    HTTP_TIMEOUT = "TWELVE_DATA_HTTP_TIMEOUT"
    HTTP_TRANSIENT_FAILURE = "TWELVE_DATA_HTTP_TRANSIENT_FAILURE"
    HTTP_PERMANENT_FAILURE = "TWELVE_DATA_HTTP_PERMANENT_FAILURE"
    AUTHENTICATION_REJECTED = "TWELVE_DATA_AUTHENTICATION_REJECTED"
    ACCESS_FORBIDDEN = "TWELVE_DATA_ACCESS_FORBIDDEN"
    INSTRUMENT_NOT_FOUND = "TWELVE_DATA_INSTRUMENT_NOT_FOUND"
    PROVIDER_REJECTED_REQUEST = "TWELVE_DATA_PROVIDER_REJECTED_REQUEST"
    RESPONSE_SCHEMA_INVALID = "TWELVE_DATA_RESPONSE_SCHEMA_INVALID"
    RESPONSE_VALUE_INVALID = "TWELVE_DATA_RESPONSE_VALUE_INVALID"
    ADJUSTMENT_UNSUPPORTED = "TWELVE_DATA_ADJUSTMENT_UNSUPPORTED"
    NO_DATA = "TWELVE_DATA_NO_DATA"


class TwelveDataProviderError(RuntimeError):
    """Expose only stable, non-sensitive provider diagnostics."""

    def __init__(
        self,
        category: TwelveDataErrorCategory,
        operation: str = "time_series",
        *,
        http_status: int | None = None,
        provider_code: int | None = None,
        safe_parameter_hint: str | None = None,
    ) -> None:
        self.category = category
        self.operation = operation if operation == "time_series" else "unknown"
        self.http_status = _safe_integer(http_status)
        self.provider_code = _safe_integer(provider_code)
        self.safe_parameter_hint = _safe_parameter_hint(safe_parameter_hint)
        super().__init__(self._safe_message())

    def __repr__(self) -> str:
        return f"TwelveDataProviderError({self._safe_message()})"

    def _safe_message(self) -> str:
        fields = [f"category={self.category.value}", f"operation={self.operation}"]
        if self.http_status is not None:
            fields.append(f"http_status={self.http_status}")
        if self.provider_code is not None:
            fields.append(f"provider_code={self.provider_code}")
        if self.safe_parameter_hint is not None:
            fields.append(f"safe_parameter_hint={self.safe_parameter_hint}")
        return ", ".join(fields)


_SAFE_PARAMETER_HINTS = frozenset(
    {
        "adjust",
        "apikey",
        "end_date",
        "interval",
        "mic_code",
        "order",
        "outputsize",
        "start_date",
        "symbol",
        "unknown",
    }
)


def _safe_integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _safe_parameter_hint(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in _SAFE_PARAMETER_HINTS else "unknown"
