"""Positive-close label calculation and source-contract validation."""

from decimal import Decimal
from typing import Never

from auto_trading_v2.domain.feature_outcomes import (
    CALENDAR_CODE,
    CALENDAR_VERSION,
    OUTCOME_POLICY_CODE,
    OUTCOME_POLICY_VERSION,
    SOURCE_PROVIDER_CODE,
    DailyFeatureOutcome,
    ForwardReturn,
    OutcomeObservationMode,
)
from auto_trading_v2.domain.outcome_labels.errors import OutcomeLabelValidationError
from auto_trading_v2.domain.outcome_labels.outcomes import PositiveForwardCloseLabel


def positive_forward_close_label(value: ForwardReturn) -> PositiveForwardCloseLabel:
    if not isinstance(value, ForwardReturn):
        raise OutcomeLabelValidationError("FORWARD_CLOSE_RETURN_INVALID")
    if value.value > Decimal(0):
        return PositiveForwardCloseLabel.POSITIVE
    return PositiveForwardCloseLabel.NOT_POSITIVE


def validate_label_source(source: object) -> DailyFeatureOutcome:
    if not isinstance(source, DailyFeatureOutcome):
        _invalid()
    if (
        source.outcome_policy_code.value != OUTCOME_POLICY_CODE
        or source.outcome_policy_version.value != OUTCOME_POLICY_VERSION
        or source.provider_code != SOURCE_PROVIDER_CODE
        or source.calendar_code.value != CALENDAR_CODE
        or source.calendar_version.value != CALENDAR_VERSION
        or source.future_bar_count != source.horizon.value
        or source.observation_mode
        not in {OutcomeObservationMode.PROSPECTIVE, OutcomeObservationMode.RETROSPECTIVE_REPLAY}
        or not (
            source.maximum_adverse_excursion_rate.value
            <= source.forward_close_return.value
            <= source.maximum_favorable_excursion_rate.value
        )
    ):
        _invalid()
    return source


def _invalid() -> Never:
    raise OutcomeLabelValidationError("SOURCE_OUTCOME_CONTRACT_INVALID")
