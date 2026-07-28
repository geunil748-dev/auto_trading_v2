"""Production filter-evaluation ID factory using the existing ID policy."""

from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, uuid5

from auto_trading_v2.domain.primitives import (
    ClientOrderID,
    DecisionID,
    FeatureSnapshotID,
    FillID,
    FilterEvaluationID,
    IdentifierFactory,
    OrderID,
    PositionEventID,
    PositionID,
    RecommendationID,
    TradeIntentID,
)

TRADE_INTENT_CLIENT_ORDER_ID_POLICY_NAME = "TRADE_INTENT_CLIENT_ORDER_ID"
TRADE_INTENT_CLIENT_ORDER_ID_POLICY_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class UuidFilterEvaluationIDFactory:
    """Adapt the replaceable generic UUID policy to the precise application port."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> FilterEvaluationID:
        return self.identifier_factory.new(FilterEvaluationID)


@dataclass(frozen=True, slots=True)
class UuidFeatureSnapshotIDFactory:
    """Adapt the existing UUID policy to canonical FeatureSnapshot IDs."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> FeatureSnapshotID:
        return self.identifier_factory.new(FeatureSnapshotID)


@dataclass(frozen=True, slots=True)
class UuidRecommendationIDFactory:
    """Adapt the existing UUID policy to canonical Recommendation IDs."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> RecommendationID:
        return self.identifier_factory.new(RecommendationID)


@dataclass(frozen=True, slots=True)
class UuidDecisionIDFactory:
    """Adapt the existing UUID policy to the decision-specific port."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> DecisionID:
        return self.identifier_factory.new(DecisionID)


@dataclass(frozen=True, slots=True)
class UuidTradeIntentIDFactory:
    """Adapt the existing UUID policy to the trade-intent-specific port."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> TradeIntentID:
        return self.identifier_factory.new(TradeIntentID)


@dataclass(frozen=True, slots=True)
class Uuid5ClientOrderIDFactory:
    """Create the exact deterministic v1 client-order identity."""

    def for_trade_intent(self, trade_intent_id: TradeIntentID) -> ClientOrderID:
        name = f"urn:auto-trading-v2:client-order:v1:{trade_intent_id.serialize()}"
        return ClientOrderID(uuid5(NAMESPACE_URL, name))


@dataclass(frozen=True, slots=True)
class UuidOrderIDFactory:
    """Adapt the existing UUID policy to canonical PaperOrder IDs."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> OrderID:
        return self.identifier_factory.new(OrderID)


@dataclass(frozen=True, slots=True)
class UuidFillIDFactory:
    """Adapt the existing UUID policy to canonical PaperFill IDs."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> FillID:
        return self.identifier_factory.new(FillID)


@dataclass(frozen=True, slots=True)
class UuidPositionIDFactory:
    """Adapt the existing UUID policy to canonical PaperPosition IDs."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> PositionID:
        return self.identifier_factory.new(PositionID)


@dataclass(frozen=True, slots=True)
class UuidPositionEventIDFactory:
    """Adapt the existing UUID policy to immutable PositionEvent IDs."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> PositionEventID:
        return self.identifier_factory.new(PositionEventID)
