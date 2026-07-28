"""Independent, secret-safe Twelve Data market-data settings."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from auto_trading_v2.config.errors import InvalidSettingError
from auto_trading_v2.config.loader import _read_env_file, repository_env_file
from auto_trading_v2.config.models import SecretValue
from auto_trading_v2.config.twelve_data_keys import (
    TWELVE_DATA_API_KEY,
    TWELVE_DATA_BASE_URL_KEY,
    TWELVE_DATA_CONNECT_TIMEOUT_KEY,
    TWELVE_DATA_CREDITS_PER_MINUTE_KEY,
    TWELVE_DATA_DAILY_CREDIT_BUDGET_KEY,
    TWELVE_DATA_ENABLED_KEY,
    TWELVE_DATA_MAXIMUM_REQUESTS_KEY,
    TWELVE_DATA_MAXIMUM_RETRY_ATTEMPTS_KEY,
    TWELVE_DATA_READ_TIMEOUT_KEY,
)
from auto_trading_v2.config.validation import parse_boolean, require_text, validate_https_url

_DEFAULTS = {
    TWELVE_DATA_ENABLED_KEY: "false",
    TWELVE_DATA_BASE_URL_KEY: "https://api.twelvedata.com",
    TWELVE_DATA_CONNECT_TIMEOUT_KEY: "5",
    TWELVE_DATA_READ_TIMEOUT_KEY: "15",
    TWELVE_DATA_CREDITS_PER_MINUTE_KEY: "8",
    TWELVE_DATA_DAILY_CREDIT_BUDGET_KEY: "800",
    TWELVE_DATA_MAXIMUM_RETRY_ATTEMPTS_KEY: "3",
    TWELVE_DATA_MAXIMUM_REQUESTS_KEY: "1",
}


@dataclass(frozen=True, slots=True, repr=False)
class TwelveDataMarketDataSettings:
    enabled: bool
    base_url: str
    api_key: SecretValue | None
    connect_timeout_seconds: float
    read_timeout_seconds: float
    credits_per_minute: int
    daily_credit_budget: int
    maximum_retry_attempts: int
    maximum_requests_per_operation: int

    def __repr__(self) -> str:
        return (
            "TwelveDataMarketDataSettings("
            f"enabled={self.enabled!r}, "
            f"api_key_configured={self.api_key is not None!r}, "
            f"connect_timeout_seconds={self.connect_timeout_seconds!r}, "
            f"read_timeout_seconds={self.read_timeout_seconds!r}, "
            f"credits_per_minute={self.credits_per_minute!r}, "
            f"daily_credit_budget={self.daily_credit_budget!r}, "
            f"maximum_retry_attempts={self.maximum_retry_attempts!r}, "
            f"maximum_requests_per_operation={self.maximum_requests_per_operation!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def load_twelve_data_market_data_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> TwelveDataMarketDataSettings:
    """Load explicit, repository dotenv, process, then safe defaults without I/O."""

    selected = _select_env_file(env_file)
    dotenv = _read_env_file(selected)
    explicit = {} if environ is None else environ
    process = os.environ if process_environ is None else process_environ

    def get(key: str) -> str | None:
        if key in explicit:
            return explicit[key]
        if key in dotenv:
            return dotenv[key]
        if key in process:
            return process[key]
        return _DEFAULTS.get(key)

    enabled = parse_boolean(
        TWELVE_DATA_ENABLED_KEY,
        require_text(TWELVE_DATA_ENABLED_KEY, get(TWELVE_DATA_ENABLED_KEY)),
    )
    base_url = validate_https_url(
        TWELVE_DATA_BASE_URL_KEY,
        require_text(TWELVE_DATA_BASE_URL_KEY, get(TWELVE_DATA_BASE_URL_KEY)),
    )
    api_key_raw = get(TWELVE_DATA_API_KEY)
    api_key = SecretValue(require_text(TWELVE_DATA_API_KEY, api_key_raw)) if enabled else None
    return TwelveDataMarketDataSettings(
        enabled=enabled,
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        connect_timeout_seconds=_bounded_float(
            TWELVE_DATA_CONNECT_TIMEOUT_KEY,
            get(TWELVE_DATA_CONNECT_TIMEOUT_KEY),
            minimum=0.1,
            maximum=60.0,
        ),
        read_timeout_seconds=_bounded_float(
            TWELVE_DATA_READ_TIMEOUT_KEY,
            get(TWELVE_DATA_READ_TIMEOUT_KEY),
            minimum=0.1,
            maximum=120.0,
        ),
        credits_per_minute=_bounded_int(
            TWELVE_DATA_CREDITS_PER_MINUTE_KEY,
            get(TWELVE_DATA_CREDITS_PER_MINUTE_KEY),
            minimum=1,
            maximum=100_000,
        ),
        daily_credit_budget=_bounded_int(
            TWELVE_DATA_DAILY_CREDIT_BUDGET_KEY,
            get(TWELVE_DATA_DAILY_CREDIT_BUDGET_KEY),
            minimum=1,
            maximum=10_000_000,
        ),
        maximum_retry_attempts=_bounded_int(
            TWELVE_DATA_MAXIMUM_RETRY_ATTEMPTS_KEY,
            get(TWELVE_DATA_MAXIMUM_RETRY_ATTEMPTS_KEY),
            minimum=1,
            maximum=5,
        ),
        maximum_requests_per_operation=_bounded_int(
            TWELVE_DATA_MAXIMUM_REQUESTS_KEY,
            get(TWELVE_DATA_MAXIMUM_REQUESTS_KEY),
            minimum=1,
            maximum=20,
        ),
    )


def _select_env_file(env_file: Path | None) -> Path:
    if env_file is None:
        return repository_env_file()
    return env_file if env_file.is_absolute() else repository_env_file().parent / env_file


def _bounded_float(key: str, raw: str | None, *, minimum: float, maximum: float) -> float:
    value = require_text(key, raw)
    try:
        parsed = float(value)
    except ValueError:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}") from None
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}")
    return parsed


def _bounded_int(key: str, raw: str | None, *, minimum: int, maximum: int) -> int:
    value = require_text(key, raw)
    try:
        parsed = int(value)
    except ValueError:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}") from None
    if str(parsed) != value.strip() or not minimum <= parsed <= maximum:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}")
    return parsed
