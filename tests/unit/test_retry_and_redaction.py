from typing import Any

import pytest

from auto_trading_v2.common.retry import RetryPolicy, call_with_retry
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.observability.redaction import REDACTED, sanitize_event_details


class RetryableFailure(RuntimeError):
    pass


class PermanentFailure(RuntimeError):
    pass


def test_retry_first_attempt_preserves_operation_result() -> None:
    expected = {"value": 7}
    sleeps: list[float] = []

    result = call_with_retry(
        lambda: expected,
        RetryPolicy(max_attempts=3),
        sleeper=sleeps.append,
    )

    assert result is expected
    assert sleeps == [0.0]


def test_retry_succeeds_and_uses_injected_sleeper() -> None:
    attempts = 0
    sleeps: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RetryableFailure("temporary")
        return "ok"

    result = call_with_retry(
        operation,
        RetryPolicy(
            max_attempts=3,
            retry_delay_seconds=0.25,
            request_delay_seconds=0.1,
        ),
        retryable_exceptions=(RetryableFailure,),
        sleeper=sleeps.append,
    )

    assert result == "ok"
    assert attempts == 3
    assert sleeps == [0.1, 0.25, 0.25]


def test_retry_preserves_original_final_exception() -> None:
    failure = RetryableFailure("last")

    def operation() -> None:
        raise failure

    with pytest.raises(RetryableFailure) as caught:
        call_with_retry(
            operation,
            RetryPolicy(max_attempts=2),
            retryable_exceptions=(RetryableFailure,),
            sleeper=lambda _: None,
        )

    assert caught.value is failure


def test_non_retryable_exception_is_raised_immediately() -> None:
    attempts = 0
    sleeps: list[float] = []

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise PermanentFailure("stop")

    with pytest.raises(PermanentFailure):
        call_with_retry(
            operation,
            RetryPolicy(max_attempts=3),
            retryable_exceptions=(RetryableFailure,),
            sleeper=sleeps.append,
        )

    assert attempts == 1
    assert sleeps == [0.0]


@pytest.mark.parametrize(
    ("max_attempts", "delay"),
    [(0, 0.0), (True, 0.0), (1, -1.0), (1, float("inf"))],
)
def test_retry_policy_rejects_invalid_values(max_attempts: int, delay: float) -> None:
    with pytest.raises(ValidationError):
        RetryPolicy(max_attempts=max_attempts, retry_delay_seconds=delay)


def test_redaction_is_recursive_case_insensitive_and_non_mutating() -> None:
    original: dict[str, Any] = {
        "Authorization": "Bearer abc",
        "nested": [
            {"app-key": "key", "approval_key": "approval", "safe": "visible"},
            ({"AccountNo": "123"}, {"PASSWORD": "pw"}),
        ],
    }

    sanitized = sanitize_event_details(original)

    assert sanitized == {
        "Authorization": REDACTED,
        "nested": [
            {"app-key": REDACTED, "approval_key": REDACTED, "safe": "visible"},
            ({"AccountNo": REDACTED}, {"PASSWORD": REDACTED}),
        ],
    }
    assert original["Authorization"] == "Bearer abc"
    assert original["nested"][0]["app-key"] == "key"


def test_redaction_supports_custom_placeholder() -> None:
    assert sanitize_event_details({"token": "abc"}, "***") == {"token": "***"}


def test_redaction_result_repr_does_not_expose_sensitive_values() -> None:
    sensitive_value = "credential-that-must-not-leak"

    sanitized = sanitize_event_details(
        {"token": sensitive_value, "nested": {"Password": sensitive_value}}
    )

    assert sensitive_value not in repr(sanitized)
    assert sanitized == {"token": REDACTED, "nested": {"Password": REDACTED}}
