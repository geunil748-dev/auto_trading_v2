"""Safe strategy-decision domain errors."""

from auto_trading_v2.domain.errors import ValidationError


class StrategyValidationError(ValidationError):
    """A strategy policy, signal, or result violated its contract."""


class StrategySignalMismatchError(StrategyValidationError):
    """A signal does not match the strategy's required filter identity."""
