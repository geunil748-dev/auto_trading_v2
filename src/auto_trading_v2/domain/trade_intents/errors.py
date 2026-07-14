"""Safe validation failures for deterministic trade-intent policy."""

from auto_trading_v2.domain.errors import ValidationError


class TradeIntentValidationError(ValidationError):
    """A trade-intent policy or result violates its public contract."""
