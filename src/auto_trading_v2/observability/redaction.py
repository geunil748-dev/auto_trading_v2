"""Recursive, non-mutating redaction for structured observability data."""

from collections.abc import Mapping
from typing import Any

REDACTED = "<redacted>"
_SENSITIVE_KEY_PARTS = (
    "acnt_prdt_cd",
    "account",
    "app_key",
    "appkey",
    "app_secret",
    "appsecret",
    "approval",
    "authorization",
    "bearer",
    "cano",
    "chat_id",
    "chatid",
    "credential",
    "dsn",
    "passwd",
    "password",
    "secret",
    "token",
)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def sanitize_event_details(value: Any, placeholder: str = REDACTED) -> Any:
    """Return a redacted copy of nested mappings, lists, and tuples."""

    if isinstance(value, Mapping):
        return {
            key: (
                placeholder if _is_sensitive_key(key) else sanitize_event_details(item, placeholder)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_event_details(item, placeholder) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_event_details(item, placeholder) for item in value)
    return value
