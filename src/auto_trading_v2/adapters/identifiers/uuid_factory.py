"""Production filter-evaluation ID factory using the existing ID policy."""

from dataclasses import dataclass, field

from auto_trading_v2.domain.primitives import (
    DecisionID,
    FilterEvaluationID,
    IdentifierFactory,
)


@dataclass(frozen=True, slots=True)
class UuidFilterEvaluationIDFactory:
    """Adapt the replaceable generic UUID policy to the precise application port."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> FilterEvaluationID:
        return self.identifier_factory.new(FilterEvaluationID)


@dataclass(frozen=True, slots=True)
class UuidDecisionIDFactory:
    """Adapt the existing UUID policy to the decision-specific port."""

    identifier_factory: IdentifierFactory = field(default_factory=IdentifierFactory, repr=False)

    def new(self) -> DecisionID:
        return self.identifier_factory.new(DecisionID)
