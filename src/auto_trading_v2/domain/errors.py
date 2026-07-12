"""Small, stable domain exception hierarchy."""


class DomainError(Exception):
    """Base class for domain rule violations."""


class ValidationError(DomainError, ValueError):
    """Raised when a value cannot form a valid domain object."""


class CurrencyMismatchError(DomainError):
    """Raised when arithmetic mixes different currencies."""


class InvalidTimestampError(ValidationError):
    """Raised for naive or otherwise invalid timestamps."""


class InvalidBreakoutInputError(ValidationError):
    """Raised when breakout calculation inputs violate its rules."""
