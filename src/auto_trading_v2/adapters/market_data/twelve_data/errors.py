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
    PROVIDER_REJECTED_REQUEST = "TWELVE_DATA_PROVIDER_REJECTED_REQUEST"
    RESPONSE_SCHEMA_INVALID = "TWELVE_DATA_RESPONSE_SCHEMA_INVALID"
    RESPONSE_VALUE_INVALID = "TWELVE_DATA_RESPONSE_VALUE_INVALID"
    ADJUSTMENT_UNSUPPORTED = "TWELVE_DATA_ADJUSTMENT_UNSUPPORTED"
    NO_DATA = "TWELVE_DATA_NO_DATA"


class TwelveDataProviderError(RuntimeError):
    """Expose only a stable category and non-sensitive operation label."""

    def __init__(
        self,
        category: TwelveDataErrorCategory,
        operation: str = "time_series",
    ) -> None:
        self.category = category
        self.operation = operation
        super().__init__(f"{category.value}: {operation}")

    def __repr__(self) -> str:
        return (
            "TwelveDataProviderError("
            f"category={self.category.value!r}, operation={self.operation!r})"
        )
