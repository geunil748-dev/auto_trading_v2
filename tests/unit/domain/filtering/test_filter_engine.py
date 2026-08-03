from decimal import Decimal

from auto_trading_v2.domain.filtering.engine import DeterministicFilterEngine
from auto_trading_v2.domain.filtering.models import FilterOutcome, FilterSetName

from .helpers import definition, evaluate_all, filter_input, with_weights


def test_all_pass_scores_100_and_passes_every_policy() -> None:
    results = evaluate_all(filter_input())

    assert all(result.score == Decimal("100") for result in results.values())
    assert all(result.passed for result in results.values())
    assert all(
        check.outcome is FilterOutcome.PASS for check in results[FilterSetName.STRICT].checks
    )


def test_breakout_only_failure_has_score_70_and_expected_policy_results() -> None:
    results = evaluate_all(filter_input(last_price="24"))

    assert all(result.score == Decimal("70") for result in results.values())
    assert not results[FilterSetName.STRICT].passed
    assert results[FilterSetName.BALANCED].passed
    assert results[FilterSetName.SCORE_ONLY].passed
    assert results[FilterSetName.OBSERVATION].passed


def test_missing_previous_close_is_distinct_and_score_only_passes_at_60() -> None:
    results = evaluate_all(filter_input(previous_close=None))

    strict = results[FilterSetName.STRICT]
    assert strict.checks[1].outcome is FilterOutcome.NOT_EVALUABLE
    assert strict.checks[2].outcome is FilterOutcome.NOT_EVALUABLE
    assert strict.score == Decimal("60")
    assert not strict.passed
    assert not results[FilterSetName.BALANCED].passed
    assert results[FilterSetName.SCORE_ONLY].passed
    assert results[FilterSetName.OBSERVATION].passed


def test_price_range_failure_blocks_hard_policies_but_not_score_or_observation() -> None:
    value = filter_input(
        open_price="309",
        last_price="301",
        previous_high="200",
        previous_low="100",
        previous_close="300",
    )
    results = evaluate_all(value)

    assert results[FilterSetName.STRICT].score == Decimal("80")
    assert not results[FilterSetName.STRICT].passed
    assert not results[FilterSetName.BALANCED].passed
    assert results[FilterSetName.SCORE_ONLY].passed
    assert results[FilterSetName.OBSERVATION].passed


def test_balanced_score_69_fails_and_score_only_59_fails() -> None:
    engine = DeterministicFilterEngine()
    breakout_failure = filter_input(last_price="24")
    balanced_69 = with_weights(definition(FilterSetName.BALANCED), ("20", "20", "20", "31", "9"))
    missing_close = filter_input(previous_close=None)
    score_only_59 = with_weights(
        definition(FilterSetName.SCORE_ONLY), ("20", "21", "20", "30", "9")
    )

    assert engine.evaluate(breakout_failure, balanced_69).score == Decimal("69")
    assert not engine.evaluate(breakout_failure, balanced_69).passed
    assert engine.evaluate(missing_close, score_only_59).score == Decimal("59")
    assert not engine.evaluate(missing_close, score_only_59).passed


def test_observation_always_passes_and_never_has_blocking_reasons() -> None:
    value = filter_input(
        open_price="100",
        last_price="301",
        previous_high="400",
        previous_low="200",
        previous_close=None,
        volume=0,
    )
    result = DeterministicFilterEngine().evaluate(value, definition(FilterSetName.OBSERVATION))

    assert result.passed
    assert result.score == Decimal("0")
    assert result.blocking_reason_codes == ()
