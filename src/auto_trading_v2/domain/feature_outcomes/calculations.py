"""Decimal-only raw forward-path calculations and contract checks."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from auto_trading_v2.domain.daily_market_bars import (
    DailyMarketBar,
    DailyMarketBarAdjustmentBasis,
)
from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)
from auto_trading_v2.domain.feature_outcomes.outcomes import OutcomeObservationMode
from auto_trading_v2.domain.feature_outcomes.policies import SOURCE_PROVIDER_CODE
from auto_trading_v2.domain.feature_outcomes.provenance import (
    FutureBarProvenanceEntry,
    canonical_future_bar_provenance,
)
from auto_trading_v2.domain.feature_outcomes.values import (
    OUTCOME_DECIMAL_CONTEXT,
    ExcursionRate,
    ForwardReturn,
    canonical_outcome_price,
)
from auto_trading_v2.domain.primitives import SessionDate, Symbol


@dataclass(frozen=True, slots=True)
class CalculatedForwardOutcome:
    terminal_close: Decimal
    forward_close_return: ForwardReturn
    maximum_favorable_excursion_rate: ExcursionRate
    maximum_adverse_excursion_rate: ExcursionRate
    terminal_session_date: SessionDate
    future_bar_provenance: tuple[FutureBarProvenanceEntry, ...]
    latest_input_available_at: datetime


def calculate_forward_outcome(
    reference_close: Decimal,
    bars: tuple[DailyMarketBar, ...],
    expected_sessions: tuple[SessionDate, ...],
    symbol: Symbol,
    observation_as_of: datetime,
) -> CalculatedForwardOutcome:
    reference = canonical_outcome_price(reference_close, "REFERENCE_CLOSE_INVALID")
    _validate_sessions(bars, expected_sessions)
    _validate_bar_contract(bars, symbol, observation_as_of)
    with localcontext(OUTCOME_DECIMAL_CONTEXT):
        terminal = bars[-1].bar_input.close_price
        forward = terminal / reference - Decimal(1)
        favorable = max(bar.bar_input.high_price / reference - Decimal(1) for bar in bars)
        adverse = min(bar.bar_input.low_price / reference - Decimal(1) for bar in bars)
    forward_value = ForwardReturn(forward)
    favorable_value = ExcursionRate(favorable)
    adverse_value = ExcursionRate(adverse)
    if not adverse_value.value <= forward_value.value <= favorable_value.value:
        _invalid("OUTCOME_RATE_RELATION_INVALID")
    provenance = canonical_future_bar_provenance(
        tuple(
            FutureBarProvenanceEntry(
                bar.daily_market_bar_id,
                bar.bar_input.session_date,
                bar.bar_input.source_code,
                bar.bar_input.source_record_key,
                bar.bar_input.source_version,
                bar.bar_input.available_at,
                bar.content_digest,
            )
            for bar in bars
        )
    )
    return CalculatedForwardOutcome(
        canonical_outcome_price(terminal, "TERMINAL_CLOSE_INVALID"),
        forward_value,
        favorable_value,
        adverse_value,
        expected_sessions[-1],
        provenance,
        max(entry.available_at for entry in provenance),
    )


def observation_mode(
    scoring_generated_at: datetime,
    first_future_session_open_at: datetime,
) -> OutcomeObservationMode:
    return (
        OutcomeObservationMode.PROSPECTIVE
        if scoring_generated_at <= first_future_session_open_at
        else OutcomeObservationMode.RETROSPECTIVE_REPLAY
    )


def _validate_sessions(
    bars: tuple[DailyMarketBar, ...],
    expected_sessions: tuple[SessionDate, ...],
) -> None:
    if not 1 <= len(expected_sessions) <= 5:
        _invalid("OUTCOME_HORIZON_INVALID")
    actual = tuple(bar.bar_input.session_date for bar in bars)
    if len(bars) != len(expected_sessions) or actual != expected_sessions:
        _invalid("FUTURE_BARS_INCOMPLETE")
    if len(set(actual)) != len(actual):
        _invalid("FUTURE_BARS_INCOMPLETE")


def _validate_bar_contract(
    bars: tuple[DailyMarketBar, ...],
    symbol: Symbol,
    observation_as_of: datetime,
) -> None:
    for bar in bars:
        source = bar.bar_input
        if (
            source.source_code != SOURCE_PROVIDER_CODE
            or source.symbol != symbol
            or source.adjustment_basis is not DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
            or source.currency.code != "USD"
            or source.available_at > observation_as_of
            or source.observed_at > source.available_at
        ):
            _invalid("FUTURE_BAR_CONTRACT_INVALID")


def _invalid(category: str) -> None:
    raise OutcomeObservationValidationError(category)
