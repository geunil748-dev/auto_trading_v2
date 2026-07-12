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
    __slots__ = ()


class FilterSetID(_UUIDIdentifier):
    __slots__ = ()


class RunID(_UUIDIdentifier):
    __slots__ = ()


class CandidateID(_UUIDIdentifier):
    __slots__ = ()


class DecisionID(_UUIDIdentifier):
    __slots__ = ()


class TradeIntentID(_UUIDIdentifier):
    __slots__ = ()


class ClientOrderID(_UUIDIdentifier):
    __slots__ = ()


class OrderID(_UUIDIdentifier):
    __slots__ = ()


class FillID(_UUIDIdentifier):
    __slots__ = ()


class PositionID(_UUIDIdentifier):
    __slots__ = ()


class EventID(_UUIDIdentifier):
    __slots__ = ()


class NotificationID(_UUIDIdentifier):
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
