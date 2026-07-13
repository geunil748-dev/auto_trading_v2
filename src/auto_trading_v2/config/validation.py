"""Pure configuration parsers that never return raw values in errors."""

from __future__ import annotations

from collections.abc import Collection
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from auto_trading_v2.config.errors import InvalidSettingError, MissingSettingError
from auto_trading_v2.config.models import SecretValue

TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def require_text(key: str, value: str | None) -> str:
    """Return trimmed non-empty text or raise a value-free missing error."""

    if value is None or not value.strip():
        raise MissingSettingError(key)
    return value.strip()


def parse_boolean(key: str, value: str) -> bool:
    """Parse only the documented case-insensitive boolean spellings."""

    normalized = value.strip().casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise InvalidSettingError(key, "must be one of: true, 1, yes, on, false, 0, no, off")


def normalize_choice(key: str, value: str, allowed: Collection[str]) -> str:
    """Normalize a case-insensitive choice and report only allowed values."""

    normalized = value.strip().casefold()
    accepted = {item.casefold(): item for item in allowed}
    if normalized not in accepted:
        rendered = ", ".join(sorted(allowed))
        raise InvalidSettingError(key, f"must be one of: {rendered}")
    return accepted[normalized]


def validate_mssql_url(key: str, value: str, *, expected_database: str) -> SecretValue:
    """Validate MSSQL dialect and database without exposing connection details."""

    raw = require_text(key, value)
    try:
        parsed = make_url(raw)
        driver_value = parsed.query.get("driver")
    except (ArgumentError, TypeError, ValueError):
        raise InvalidSettingError(key, "must be a valid SQLAlchemy URL") from None
    if parsed.drivername != "mssql+pyodbc":
        raise InvalidSettingError(key, "must use the mssql+pyodbc dialect")
    if parsed.database != expected_database:
        raise InvalidSettingError(key, f"must target database {expected_database}")
    if isinstance(driver_value, tuple):
        raise InvalidSettingError(key, "must declare at most one ODBC driver")
    if driver_value and "freetds" in driver_value.casefold():
        raise InvalidSettingError(key, "must not use FreeTDS")
    return SecretValue(raw)


def validate_https_url(key: str, value: str) -> str:
    """Validate an absolute HTTPS URL without user info, query, or fragment."""

    raw = require_text(key, value)
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
    except ValueError:
        raise InvalidSettingError(key, "must be an absolute HTTPS URL") from None
    if parsed.scheme.casefold() != "https" or not hostname:
        raise InvalidSettingError(key, "must be an absolute HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidSettingError(key, "must not include user information")
    if parsed.query or parsed.fragment:
        raise InvalidSettingError(key, "must not include a query or fragment")
    return raw
