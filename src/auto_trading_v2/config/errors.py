"""Credential-safe configuration error hierarchy."""

from __future__ import annotations


class ConfigurationError(ValueError):
    """Base error containing only a canonical key and a safe reason."""

    def __init__(self, key: str, reason: str) -> None:
        self.key = key
        self.reason = reason
        super().__init__(f"{key} {reason}")


class MissingSettingError(ConfigurationError):
    """Raised when a required canonical setting is absent or blank."""

    def __init__(self, key: str) -> None:
        super().__init__(key, "is required")


class InvalidSettingError(ConfigurationError):
    """Raised when a setting does not satisfy its public contract."""


class UnsafeSettingError(ConfigurationError):
    """Raised when a configuration source is unsafe to read."""
