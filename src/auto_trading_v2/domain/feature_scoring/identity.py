"""Semantic identity and canonical hashing for P4A scoring."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from auto_trading_v2.domain.feature_scoring.errors import FeatureScoringValidationError
from auto_trading_v2.domain.feature_scoring.policies import (
    RANKING_POLICY_CODE,
    RANKING_POLICY_VERSION,
    SCORING_POLICY_CODE,
    SCORING_POLICY_VERSION,
    FeatureScoringPolicyCode,
    FeatureScoringPolicyVersion,
    RankingPolicyCode,
    RankingPolicyVersion,
)
from auto_trading_v2.domain.primitives import DailyFeaturePipelineRunID


@dataclass(frozen=True, slots=True)
class DailyFeatureScoringIdentity:
    source_daily_feature_pipeline_run_id: DailyFeaturePipelineRunID
    scoring_policy_code: FeatureScoringPolicyCode
    scoring_policy_version: FeatureScoringPolicyVersion
    ranking_policy_code: RankingPolicyCode
    ranking_policy_version: RankingPolicyVersion

    def __post_init__(self) -> None:
        if not isinstance(self.source_daily_feature_pipeline_run_id, DailyFeaturePipelineRunID):
            raise FeatureScoringValidationError("SCORING_SOURCE_RUN_ID_INVALID")
        expected = (
            SCORING_POLICY_CODE,
            SCORING_POLICY_VERSION,
            RANKING_POLICY_CODE,
            RANKING_POLICY_VERSION,
        )
        actual = (
            self.scoring_policy_code.value,
            self.scoring_policy_version.value,
            self.ranking_policy_code.value,
            self.ranking_policy_version.value,
        )
        if actual != expected:
            raise FeatureScoringValidationError("SCORING_POLICY_UNSUPPORTED")


def daily_feature_scoring_run_key(identity: DailyFeatureScoringIdentity) -> str:
    payload = {
        "ranking_policy_code": identity.ranking_policy_code.value,
        "ranking_policy_version": identity.ranking_policy_version.value,
        "scoring_policy_code": identity.scoring_policy_code.value,
        "scoring_policy_version": identity.scoring_policy_version.value,
        "source_daily_feature_pipeline_run_id": (
            identity.source_daily_feature_pipeline_run_id.serialize()
        ),
    }
    return f"daily-feature-scoring-run:v1:{feature_scoring_content_digest(payload)}"


def feature_scoring_content_digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
