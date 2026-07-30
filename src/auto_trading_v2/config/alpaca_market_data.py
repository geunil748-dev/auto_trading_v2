"""Independent, secret-safe Alpaca historical market-data settings."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from auto_trading_v2.config.alpaca_market_data_keys import (
    ALPACA_API_KEY_ID_KEY,
    ALPACA_API_SECRET_KEY,
    ALPACA_BASE_URL_KEY,
    ALPACA_CONNECT_TIMEOUT_KEY,
    ALPACA_ENABLED_KEY,
    ALPACA_FEED_KEY,
    ALPACA_MAXIMUM_PAGES_KEY,
    ALPACA_MAXIMUM_RETRY_ATTEMPTS_KEY,
    ALPACA_READ_TIMEOUT_KEY,
    ALPACA_REQUESTS_PER_MINUTE_KEY,
)
from auto_trading_v2.config.errors import InvalidSettingError
from auto_trading_v2.config.loader import _read_env_file, repository_env_file
from auto_trading_v2.config.models import SecretValue
from auto_trading_v2.config.validation import (
    normalize_choice,
    parse_boolean,
    require_text,
    validate_https_url,
)

_DEFAULTS = {
    ALPACA_ENABLED_KEY: "false",
    ALPACA_BASE_URL_KEY: "https://data.alpaca.markets",
    ALPACA_FEED_KEY: "iex",
    ALPACA_CONNECT_TIMEOUT_KEY: "5",
    ALPACA_READ_TIMEOUT_KEY: "15",
    ALPACA_REQUESTS_PER_MINUTE_KEY: "200",
    ALPACA_MAXIMUM_RETRY_ATTEMPTS_KEY: "3",
    ALPACA_MAXIMUM_PAGES_KEY: "5",
}


@dataclass(frozen=True, slots=True, repr=False)
class AlpacaMarketDataSettings:
    enabled: bool
    base_url: str
    api_key_id: SecretValue | None
    api_secret_key: SecretValue | None
    feed: str
    connect_timeout_seconds: float
    read_timeout_seconds: float
    requests_per_minute: int
    maximum_retry_attempts: int
    maximum_pages: int

    def __repr__(self) -> str:
        return (
            "AlpacaMarketDataSettings("
            f"enabled={self.enabled!r}, "
            f"api_key_id_configured={self.api_key_id is not None!r}, "
            f"api_secret_key_configured={self.api_secret_key is not None!r}, "
            f"feed={self.feed!r}, "
            f"connect_timeout_seconds={self.connect_timeout_seconds!r}, "
            f"read_timeout_seconds={self.read_timeout_seconds!r}, "
            f"requests_per_minute={self.requests_per_minute!r}, "
            f"maximum_retry_attempts={self.maximum_retry_attempts!r}, "
            f"maximum_pages={self.maximum_pages!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def load_alpaca_market_data_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    process_environ: Mapping[str, str] | None = None,
) -> AlpacaMarketDataSettings:
    """Load explicit, repository dotenv, process, then safe defaults."""

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
        ALPACA_ENABLED_KEY,
        require_text(ALPACA_ENABLED_KEY, get(ALPACA_ENABLED_KEY)),
    )
    base_url = _exact_data_host(
        validate_https_url(
            ALPACA_BASE_URL_KEY,
            require_text(ALPACA_BASE_URL_KEY, get(ALPACA_BASE_URL_KEY)),
        )
    )
    key_id = (
        SecretValue(require_text(ALPACA_API_KEY_ID_KEY, get(ALPACA_API_KEY_ID_KEY)))
        if enabled
        else None
    )
    secret = (
        SecretValue(require_text(ALPACA_API_SECRET_KEY, get(ALPACA_API_SECRET_KEY)))
        if enabled
        else None
    )
    return AlpacaMarketDataSettings(
        enabled=enabled,
        base_url=base_url,
        api_key_id=key_id,
        api_secret_key=secret,
        feed=normalize_choice(
            ALPACA_FEED_KEY,
            require_text(ALPACA_FEED_KEY, get(ALPACA_FEED_KEY)),
            {"iex"},
        ),
        connect_timeout_seconds=_bounded_float(
            ALPACA_CONNECT_TIMEOUT_KEY, get(ALPACA_CONNECT_TIMEOUT_KEY), 0.1, 60.0
        ),
        read_timeout_seconds=_bounded_float(
            ALPACA_READ_TIMEOUT_KEY, get(ALPACA_READ_TIMEOUT_KEY), 0.1, 120.0
        ),
        requests_per_minute=_bounded_int(
            ALPACA_REQUESTS_PER_MINUTE_KEY, get(ALPACA_REQUESTS_PER_MINUTE_KEY), 1, 100_000
        ),
        maximum_retry_attempts=_bounded_int(
            ALPACA_MAXIMUM_RETRY_ATTEMPTS_KEY,
            get(ALPACA_MAXIMUM_RETRY_ATTEMPTS_KEY),
            1,
            5,
        ),
        maximum_pages=_bounded_int(ALPACA_MAXIMUM_PAGES_KEY, get(ALPACA_MAXIMUM_PAGES_KEY), 1, 100),
    )


def _select_env_file(env_file: Path | None) -> Path:
    if env_file is None:
        return repository_env_file()
    return env_file if env_file.is_absolute() else repository_env_file().parent / env_file


def _exact_data_host(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise InvalidSettingError(
            ALPACA_BASE_URL_KEY,
            "must be exactly the official Alpaca data host",
        ) from None
    if parsed.hostname != "data.alpaca.markets" or port is not None or parsed.path not in {"", "/"}:
        raise InvalidSettingError(
            ALPACA_BASE_URL_KEY,
            "must be exactly the official Alpaca data host",
        )
    return "https://data.alpaca.markets"


def _bounded_float(key: str, raw: str | None, minimum: float, maximum: float) -> float:
    value = require_text(key, raw)
    try:
        parsed = float(value)
    except ValueError:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}") from None
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}")
    return parsed


def _bounded_int(key: str, raw: str | None, minimum: int, maximum: int) -> int:
    value = require_text(key, raw)
    try:
        parsed = int(value)
    except ValueError:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}") from None
    if str(parsed) != value.strip() or not minimum <= parsed <= maximum:
        raise InvalidSettingError(key, f"must be between {minimum} and {maximum}")
    return parsed
