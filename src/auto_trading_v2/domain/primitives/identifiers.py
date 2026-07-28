"""Type-distinct UUID identifiers and their replaceable creation policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Self, TypeVar
from uuid import UUID, uuid4

from auto_trading_v2.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class _UUIDIdentifier:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValidationError("식별자 값은 UUID여야 합니다.")

    @classmethod
    def parse(cls, value: str) -> Self:
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValidationError("유효한 UUID 문자열이 아닙니다.") from exc
        return cls(parsed)

    def serialize(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return self.serialize()


class StrategyID(_UUIDIdentifier):
    """Identifier for a strategy definition."""

    __slots__ = ()


class FilterSetID(_UUIDIdentifier):
    """Identifier for a filter-set definition."""

    __slots__ = ()


class RunID(_UUIDIdentifier):
    """Identifier for one execution run."""

    __slots__ = ()


class CandidateID(_UUIDIdentifier):
    """Identifier for a trading candidate."""

    __slots__ = ()


class MarketSnapshotID(_UUIDIdentifier):
    """Identifier for a canonical market observation."""

    __slots__ = ()


class DailyMarketBarID(_UUIDIdentifier):
    """Identifier for a canonical completed daily market bar."""

    __slots__ = ()


class FeatureSnapshotID(_UUIDIdentifier):
    """Identifier for a canonical Point-in-Time feature bundle."""

    __slots__ = ()


class RecommendationID(_UUIDIdentifier):
    """Identifier for a canonical user-facing recommendation."""

    __slots__ = ()


class FilterEvaluationID(_UUIDIdentifier):
    """Identifier for a canonical filter evaluation."""

    __slots__ = ()


class DecisionID(_UUIDIdentifier):
    """Identifier for a strategy decision."""

    __slots__ = ()


class TradeIntentID(_UUIDIdentifier):
    """Identifier for a canonical trade intent."""

    __slots__ = ()


class ClientOrderID(_UUIDIdentifier):
    """Identifier supplied by a client at an order boundary."""

    __slots__ = ()


class OrderID(_UUIDIdentifier):
    """Identifier for a canonical paper order."""

    __slots__ = ()


class FillID(_UUIDIdentifier):
    """Identifier for a canonical paper fill."""

    __slots__ = ()


class PositionID(_UUIDIdentifier):
    """Identifier for a canonical PaperPosition."""

    __slots__ = ()


class PositionEventID(_UUIDIdentifier):
    """Identifier for an immutable position change event."""

    __slots__ = ()


class EquitySnapshotID(_UUIDIdentifier):
    """Identifier for a canonical account-equity observation."""

    __slots__ = ()


class EventID(_UUIDIdentifier):
    """Identifier for a domain or integration event."""

    __slots__ = ()


class NotificationID(_UUIDIdentifier):
    """Identifier reserved for a future notification."""

    __slots__ = ()


IdentifierT = TypeVar("IdentifierT", bound=_UUIDIdentifier)


class IdentifierFactory:
    """Create typed IDs behind a replaceable UUID generation policy."""

    def __init__(self, generator: Callable[[], UUID] = uuid4) -> None:
        self._generator = generator

    def new(self, identifier_type: type[IdentifierT]) -> IdentifierT:
        if not issubclass(identifier_type, _UUIDIdentifier):
            raise TypeError("지원되는 식별자 타입이 아닙니다.")
        return identifier_type(self._generator())
