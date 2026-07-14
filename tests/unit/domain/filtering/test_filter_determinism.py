from decimal import getcontext, setcontext

from auto_trading_v2.domain.filtering.catalog import BALANCED
from auto_trading_v2.domain.filtering.details import serialize_filter_evaluation_details
from auto_trading_v2.domain.filtering.engine import DeterministicFilterEngine
from auto_trading_v2.domain.filtering.models import CHECK_ORDER

from .helpers import filter_input


def test_repeated_evaluation_and_serialization_are_identical() -> None:
    engine = DeterministicFilterEngine()
    value = filter_input(open_price="22.660000000000000000")

    first = engine.evaluate(value, BALANCED)
    second = engine.evaluate(value, BALANCED)

    assert first == second
    assert tuple(check.name for check in first.checks) == CHECK_ORDER
    assert serialize_filter_evaluation_details(first) == serialize_filter_evaluation_details(second)


def test_external_decimal_context_does_not_change_results() -> None:
    original = getcontext().copy()
    engine = DeterministicFilterEngine()
    value = filter_input(open_price="22.660000000000000000")
    try:
        getcontext().prec = 6
        low_precision = engine.evaluate(value, BALANCED)
        getcontext().prec = 50
        high_precision = engine.evaluate(value, BALANCED)
    finally:
        setcontext(original)

    assert low_precision == high_precision
    assert serialize_filter_evaluation_details(
        low_precision
    ) == serialize_filter_evaluation_details(high_precision)
