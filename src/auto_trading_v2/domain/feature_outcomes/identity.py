"""Semantic identities and canonical hashes for P4B.1 outcomes."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)
from auto_trading_v2.domain.feature_outcomes.policies import (
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    OutcomeObservationPolicyCode,
    OutcomeObservationPolicyVersion,
)
from auto_trading_v2.domain.feature_outcomes.provenance import (
    FutureBarProvenanceEntry,
    canonical_future_bar_provenance,
)
from auto_trading_v2.domain.feature_snapshots import TradingDayHorizon
from auto_trading_v2.domain.primitives import (
    DailyFeatureScoringItemID,
    DailyFeatureScoringRunID,
)
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class DailyFeatureOutcomeIdentity:
    source_daily_feature_scoring_item_id: DailyFeatureScoringItemID
    outcome_policy_code: OutcomeObservationPolicyCode
    outcome_policy_version: OutcomeObservationPolicyVersion
    horizon: TradingDayHorizon
    path_revision_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_daily_feature_scoring_item_id, DailyFeatureScoringItemID):
            _invalid("OUTCOME_SOURCE_SCORING_ITEM_ID_INVALID")
        if not isinstance(self.horizon, TradingDayHorizon):
            _invalid("OUTCOME_HORIZON_INVALID")
        if (
            self.outcome_policy_code.value,
            self.outcome_policy_version.value,
        ) != (OUTCOME_POLICY_CODE, OUTCOME_POLICY_VERSION):
            _invalid("OUTCOME_POLICY_UNSUPPORTED")
        if not _DIGEST.fullmatch(self.path_revision_digest):
            _invalid("PATH_REVISION_DIGEST_INVALID")


@dataclass(frozen=True, slots=True)
class OutcomeObservationRunIdentity:
    source_daily_feature_scoring_run_id: DailyFeatureScoringRunID
    outcome_policy_code: OutcomeObservationPolicyCode
    outcome_policy_version: OutcomeObservationPolicyVersion
    observation_as_of: datetime
    completion_grace_seconds: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_daily_feature_scoring_run_id, DailyFeatureScoringRunID):
            _invalid("OBSERVATION_SOURCE_SCORING_RUN_ID_INVALID")
        if (
            self.outcome_policy_code.value,
            self.outcome_policy_version.value,
        ) != (OUTCOME_POLICY_CODE, OUTCOME_POLICY_VERSION):
            _invalid("OUTCOME_POLICY_UNSUPPORTED")
        try:
            observed = normalize_utc(self.observation_as_of)
        except (TypeError, ValidationError):
            _invalid("OBSERVATION_AS_OF_INVALID")
        if (
            isinstance(self.completion_grace_seconds, bool)
            or not isinstance(self.completion_grace_seconds, int)
            or not 0 <= self.completion_grace_seconds <= 86400
        ):
            _invalid("OBSERVATION_GRACE_INVALID")
        object.__setattr__(self, "observation_as_of", observed)


def path_revision_digest(entries: tuple[FutureBarProvenanceEntry, ...]) -> str:
    ordered = canonical_future_bar_provenance(entries)
    return outcome_content_digest([entry.as_json() for entry in ordered])


def daily_feature_outcome_key(identity: DailyFeatureOutcomeIdentity) -> str:
    payload = {
        "horizon_trading_days": identity.horizon.value,
        "outcome_policy_code": identity.outcome_policy_code.value,
        "outcome_policy_version": identity.outcome_policy_version.value,
        "path_revision_digest": identity.path_revision_digest,
        "source_daily_feature_scoring_item_id": (
            identity.source_daily_feature_scoring_item_id.serialize()
        ),
    }
    return f"daily-feature-outcome:v1:{outcome_content_digest(payload)}"


def daily_feature_outcome_observation_run_key(
    identity: OutcomeObservationRunIdentity,
) -> str:
    payload = {
        "completion_grace_seconds": identity.completion_grace_seconds,
        "observation_as_of": UtcTimestamp(identity.observation_as_of).serialize(),
        "outcome_policy_code": identity.outcome_policy_code.value,
        "outcome_policy_version": identity.outcome_policy_version.value,
        "source_daily_feature_scoring_run_id": (
            identity.source_daily_feature_scoring_run_id.serialize()
        ),
    }
    return f"daily-feature-outcome-run:v1:{outcome_content_digest(payload)}"


def outcome_content_digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _invalid(category: str) -> None:
    raise OutcomeObservationValidationError(category)
