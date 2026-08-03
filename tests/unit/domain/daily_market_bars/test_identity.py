from dataclasses import replace
from datetime import timedelta, timezone
from decimal import Decimal

from auto_trading_v2.domain.daily_market_bars import (
    daily_market_bar_content_digest,
    daily_market_bar_key,
)
from tests.unit.domain.daily_market_bars.helpers import bar_input


def test_same_semantic_identity_always_has_same_exact_length_key() -> None:
    source = bar_input()
    changed = replace(source, close_price=Decimal(101))

    assert daily_market_bar_key(source) == daily_market_bar_key(changed)
    assert len(daily_market_bar_key(source)) == 84
    assert daily_market_bar_key(source).startswith("daily-market-bar:v1:")


def test_content_change_changes_digest_without_changing_key() -> None:
    source = bar_input()
    changed = replace(source, close_price=Decimal("101"))

    assert daily_market_bar_key(source) == daily_market_bar_key(changed)
    assert daily_market_bar_content_digest(source) != daily_market_bar_content_digest(changed)


def test_decimal_representation_does_not_change_digest() -> None:
    source = bar_input()
    represented = replace(
        source,
        open_price=Decimal("99.5000"),
        high_price=Decimal("102.000"),
        low_price=Decimal("98.00"),
        close_price=Decimal("100.00000"),
    )

    assert daily_market_bar_content_digest(source) == daily_market_bar_content_digest(represented)


def test_equivalent_timestamp_offsets_have_same_digest() -> None:
    source = bar_input()
    eastern = timezone(timedelta(hours=-5))
    represented = replace(
        source,
        observed_at=source.observed_at.astimezone(eastern),
        available_at=source.available_at.astimezone(eastern),
    )

    assert represented.observed_at == source.observed_at
    assert daily_market_bar_content_digest(source) == daily_market_bar_content_digest(represented)


def test_new_source_version_changes_identity_key() -> None:
    source = bar_input()

    assert daily_market_bar_key(source) != daily_market_bar_key(
        replace(source, source_version="v2")
    )
