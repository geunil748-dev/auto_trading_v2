from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

from auto_trading_v2.domain.feature_outcomes import ForwardReturn, OutcomeObservationMode
from auto_trading_v2.domain.outcome_labels import (
    DailyFeatureOutcomeLabelIdentity,
    OutcomeLabelValidationError,
    PositiveForwardCloseLabel,
    fixed_label_policy_values,
    outcome_label_key,
    positive_forward_close_label,
    validate_label_source,
)
from auto_trading_v2.domain.primitives import DailyFeatureOutcomeID
from tests.unit.p4b2a_helpers import make_label, make_outcomes


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.000001", PositiveForwardCloseLabel.POSITIVE),
        ("0", PositiveForwardCloseLabel.NOT_POSITIVE),
        ("-0.000001", PositiveForwardCloseLabel.NOT_POSITIVE),
    ],
)
def test_positive_close_policy_has_an_explicit_zero_boundary(
    value: str,
    expected: PositiveForwardCloseLabel,
) -> None:
    assert positive_forward_close_label(ForwardReturn(Decimal(value))) is expected


def test_label_preserves_prospective_source_and_deterministic_hashes() -> None:
    outcome = make_outcomes((("AAPL", "105"),))[0]

    first = make_label(outcome)
    second = make_label(outcome, identifier=40_002)

    assert first.observation_mode is OutcomeObservationMode.PROSPECTIVE
    assert first.label_value is PositiveForwardCloseLabel.POSITIVE
    assert first.label_key == second.label_key
    assert first.content_digest == second.content_digest
    assert "probability" not in first.__dataclass_fields__
    assert "recommendation" not in first.__dataclass_fields__


def test_source_outcome_revision_identity_produces_a_new_label_key() -> None:
    policy_code, policy_version = fixed_label_policy_values()
    first = DailyFeatureOutcomeLabelIdentity(
        DailyFeatureOutcomeID(UUID(int=1)), policy_code, policy_version
    )
    revision = DailyFeatureOutcomeLabelIdentity(
        DailyFeatureOutcomeID(UUID(int=2)), policy_code, policy_version
    )

    assert outcome_label_key(first) == outcome_label_key(first)
    assert outcome_label_key(first) != outcome_label_key(revision)


def test_replay_source_is_supported_but_noncanonical_source_is_rejected() -> None:
    replay = make_outcomes(
        (("AAPL", "95"),),
        mode=OutcomeObservationMode.RETROSPECTIVE_REPLAY,
    )[0]
    assert validate_label_source(replay) is replay
    assert make_label(replay).observation_mode is OutcomeObservationMode.RETROSPECTIVE_REPLAY

    invalid = replace(replay)
    object.__setattr__(invalid, "provider_code", "UNSUPPORTED")
    with pytest.raises(OutcomeLabelValidationError, match="SOURCE_OUTCOME_CONTRACT_INVALID"):
        validate_label_source(invalid)


def test_label_rejects_a_content_digest_or_source_time_shape_violation() -> None:
    outcome = make_outcomes((("AAPL", "100"),))[0]
    label = make_label(outcome)
    assert label.label_value is PositiveForwardCloseLabel.NOT_POSITIVE

    with pytest.raises(OutcomeLabelValidationError, match="LABEL_CONTENT_DIGEST_INVALID"):
        replace(label, content_digest="not-a-digest")
    with pytest.raises(OutcomeLabelValidationError, match="LABEL_TIME_ORDER_INVALID"):
        replace(label, generated_at=outcome.latest_input_available_at.replace(year=2025))
