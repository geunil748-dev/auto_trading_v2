from decimal import Decimal, getcontext

import pytest

from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.domain.feature_outcomes import (
    OutcomeObservationMode,
    OutcomeObservationValidationError,
    calculate_forward_outcome,
    observation_mode,
)
from auto_trading_v2.domain.primitives import Symbol

from .helpers import (
    OBSERVATION_AS_OF,
    SYMBOL,
    expected_sessions,
    outcome_bar,
)


@pytest.mark.parametrize(
    ("closes", "expected"),
    [
        (("110",), Decimal("0.100000000000000000")),
        (("90",), Decimal("-0.100000000000000000")),
        (("100",), Decimal("0.000000000000000000")),
        (("101", "102", "103", "104", "105"), Decimal("0.050000000000000000")),
    ],
)
def test_horizon_one_to_five_and_forward_close_return(
    closes: tuple[str, ...], expected: Decimal
) -> None:
    bars = tuple(outcome_bar(index, close=value) for index, value in enumerate(closes, 1))

    result = calculate_forward_outcome(
        Decimal("100"), bars, expected_sessions(bars), SYMBOL, OBSERVATION_AS_OF
    )

    assert result.forward_close_return.value == expected
    assert result.terminal_close == Decimal(closes[-1]).quantize(Decimal("1e-18"))
    assert result.terminal_session_date == bars[-1].bar_input.session_date
    assert len(result.future_bar_provenance) == len(closes)


def test_raw_mfe_mae_and_ordered_provenance() -> None:
    bars = (
        outcome_bar(1, close="101", high="104", low="97"),
        outcome_bar(2, close="98", high="102", low="91"),
        outcome_bar(3, close="103", high="110", low="96"),
    )

    result = calculate_forward_outcome(
        Decimal("100"), bars, expected_sessions(bars), SYMBOL, OBSERVATION_AS_OF
    )

    assert result.forward_close_return.value == Decimal("0.030000000000000000")
    assert result.maximum_favorable_excursion_rate.value == Decimal("0.100000000000000000")
    assert result.maximum_adverse_excursion_rate.value == Decimal("-0.090000000000000000")
    assert (
        result.maximum_adverse_excursion_rate.value
        <= result.forward_close_return.value
        <= result.maximum_favorable_excursion_rate.value
    )
    assert [entry.session_date for entry in result.future_bar_provenance] == list(
        expected_sessions(bars)
    )


def test_decimal_context_is_local_and_float_reference_is_rejected() -> None:
    before = getcontext().copy()
    bar = outcome_bar(1, close="100.1234567890123456789")
    result = calculate_forward_outcome(
        Decimal("99.9876543210987654321"),
        (bar,),
        expected_sessions((bar,)),
        SYMBOL,
        OBSERVATION_AS_OF,
    )

    assert result.forward_close_return.value.as_tuple().exponent == -18
    assert repr(getcontext()) == repr(before)
    with pytest.raises(OutcomeObservationValidationError, match="REFERENCE_CLOSE_INVALID"):
        calculate_forward_outcome(
            100.0,  # type: ignore[arg-type]
            (bar,),
            expected_sessions((bar,)),
            SYMBOL,
            OBSERVATION_AS_OF,
        )


@pytest.mark.parametrize(
    "mutation,category",
    [
        ("missing", "FUTURE_BARS_INCOMPLETE"),
        ("duplicate", "FUTURE_BARS_INCOMPLETE"),
        ("provider", "FUTURE_BAR_CONTRACT_INVALID"),
        ("basis", "FUTURE_BAR_CONTRACT_INVALID"),
        ("late", "FUTURE_BAR_CONTRACT_INVALID"),
        ("symbol", "FUTURE_BAR_CONTRACT_INVALID"),
    ],
)
def test_future_bar_contract_rejects_noncanonical_paths(mutation: str, category: str) -> None:
    bars = (outcome_bar(1, close="101"), outcome_bar(2, close="102"))
    expected = expected_sessions(bars)
    if mutation == "missing":
        changed = bars[:1]
    elif mutation == "duplicate":
        changed = (bars[0], bars[0])
    elif mutation == "provider":
        changed = (outcome_bar(1, close="101", source="OTHER"), bars[1])
    elif mutation == "basis":
        changed = (
            outcome_bar(
                1,
                close="101",
                basis=DailyMarketBarAdjustmentBasis.RAW,
            ),
            bars[1],
        )
    elif mutation == "late":
        changed = (
            outcome_bar(1, close="101", available_at=OBSERVATION_AS_OF.replace(day=16)),
            bars[1],
        )
    else:
        changed = (outcome_bar(1, close="101", symbol=Symbol("MSFT")), bars[1])

    with pytest.raises(OutcomeObservationValidationError, match=category):
        calculate_forward_outcome(Decimal("100"), changed, expected, SYMBOL, OBSERVATION_AS_OF)


def test_prospective_and_replay_boundary_does_not_change_math() -> None:
    first_open = OBSERVATION_AS_OF.replace(hour=13)

    assert observation_mode(first_open, first_open) is OutcomeObservationMode.PROSPECTIVE
    assert (
        observation_mode(first_open.replace(hour=12), first_open)
        is OutcomeObservationMode.PROSPECTIVE
    )
    assert (
        observation_mode(first_open.replace(hour=14), first_open)
        is OutcomeObservationMode.RETROSPECTIVE_REPLAY
    )
    assert "probability" not in calculate_forward_outcome.__annotations__
