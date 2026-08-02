from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    getcontext,
    localcontext,
    setcontext,
)

from auto_trading_v2.domain.feature_scoring import (
    ValidatedTechnicalFeatures,
    ascending_midrank_percentiles,
    calculate_component_scores,
)
from auto_trading_v2.domain.feature_snapshots import FeatureQualityStatus

from .helpers import PRICE_KEYS, VOLUME_KEYS


def candidate(value: str, *, volume: bool = True) -> ValidatedTechnicalFeatures:
    values = {key: Decimal(value) for key in PRICE_KEYS}
    values["last_close"] = Decimal("100")
    if volume:
        values.update({key: Decimal(value) for key in VOLUME_KEYS})
    return ValidatedTechnicalFeatures(values)


def test_single_value_percentile_is_one_half() -> None:
    assert ascending_midrank_percentiles({"AAPL": Decimal("10")}) == {"AAPL": Decimal("0.5")}


def test_ascending_midrank_ties_and_input_order_independence() -> None:
    first = ascending_midrank_percentiles(
        {"D": Decimal("4"), "B": Decimal("2"), "A": Decimal("2"), "C": Decimal("3")}
    )
    second = ascending_midrank_percentiles(dict(reversed(tuple(first.items()))))

    assert first == second
    with localcontext(Context(prec=38, rounding=ROUND_HALF_EVEN)):
        assert first == {
            "A": Decimal(1) / Decimal(6),
            "B": Decimal(1) / Decimal(6),
            "C": Decimal(2) / Decimal(3),
            "D": Decimal(1),
        }


def test_component_formulas_ready_weights_and_reverse_stability() -> None:
    results = calculate_component_scores(
        {"LOW": candidate("1"), "MID": candidate("2"), "HIGH": candidate("3")},
        {key: FeatureQualityStatus.READY for key in ("LOW", "MID", "HIGH")},
    )

    assert results["HIGH"].momentum == Decimal(100)
    assert results["HIGH"].trend == Decimal(100)
    assert results["HIGH"].breakout == Decimal(100)
    assert results["HIGH"].price_action == Decimal(100)
    assert results["HIGH"].stability == Decimal(0)
    assert results["HIGH"].volume == Decimal(100)
    assert results["HIGH"].overall == Decimal(90)
    assert results["MID"].overall == Decimal(50)
    assert results["LOW"].stability == Decimal(100)
    assert results["LOW"].overall == Decimal(10)


def test_degraded_volume_is_null_and_active_weights_are_renormalized() -> None:
    results = calculate_component_scores(
        {"READY": candidate("1"), "DEGRADED": candidate("2", volume=False)},
        {
            "READY": FeatureQualityStatus.READY,
            "DEGRADED": FeatureQualityStatus.DEGRADED,
        },
    )

    degraded = results["DEGRADED"]
    assert degraded.volume is None
    with localcontext(Context(prec=38, rounding=ROUND_HALF_EVEN)):
        assert degraded.overall == Decimal(8000) / Decimal(90)
    assert Decimal(0) <= degraded.overall <= Decimal(100)


def test_global_decimal_context_is_unchanged() -> None:
    original = getcontext().copy()
    custom = Context(prec=12, rounding=ROUND_DOWN)
    setcontext(custom)
    try:
        before = getcontext().copy()
        calculate_component_scores(
            {"A": candidate("1"), "B": candidate("2")},
            {"A": FeatureQualityStatus.READY, "B": FeatureQualityStatus.READY},
        )
        after = getcontext()
        assert (after.prec, after.rounding, after.Emin, after.Emax) == (
            before.prec,
            before.rounding,
            before.Emin,
            before.Emax,
        )
        assert after.flags == before.flags
        assert after.traps == before.traps
    finally:
        setcontext(original)
