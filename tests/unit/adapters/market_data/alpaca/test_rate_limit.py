import pytest

from auto_trading_v2.adapters.market_data.alpaca import AlpacaRequestRateLimiter


def test_default_rate_and_injected_wait_are_process_local() -> None:
    current = [0.0]
    sleeps: list[float] = []

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        current[0] += seconds

    limiter = AlpacaRequestRateLimiter(
        2,
        monotonic=lambda: current[0],
        sleeper=sleeper,
    )
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert sleeps == [60.0]


@pytest.mark.parametrize("value", (0, -1, True, 1.5))
def test_invalid_request_limit_is_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        AlpacaRequestRateLimiter(value)  # type: ignore[arg-type]
