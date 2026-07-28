"""Insert-only Recommendation repository boundary."""

from typing import Protocol

from auto_trading_v2.application.contracts.recommendations import NewRecommendation
from auto_trading_v2.domain.primitives import FeatureSnapshotID, RecommendationID
from auto_trading_v2.domain.recommendations import Recommendation


class RecommendationRepository(Protocol):
    def add(self, recommendation: NewRecommendation) -> Recommendation: ...

    def get_by_id(self, recommendation_id: RecommendationID) -> Recommendation | None: ...

    def get_by_recommendation_key(
        self,
        recommendation_key: str,
    ) -> Recommendation | None: ...

    def list_by_feature_snapshot_id(
        self,
        feature_snapshot_id: FeatureSnapshotID,
    ) -> tuple[Recommendation, ...]: ...
