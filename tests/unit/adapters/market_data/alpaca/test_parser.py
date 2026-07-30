from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest

from auto_trading_v2.adapters.market_data.alpaca import (
    AlpacaErrorCategory,
    AlpacaProviderError,
    AlpacaStockBarsParser,
)
from tests.unit.adapters.market_data.alpaca.helpers import NOW, fetch_request


def row(
    timestamp: object = "2026-07-17T04:00:00Z",
    *,
    close: object = Decimal("102.5"),
    volume: object = 1000,
) -> dict[str, object]:
    return {
        "t": timestamp,
        "o": Decimal("101.5"),
        "h": Decimal("104.5"),
        "l": Decimal("100.5"),
        "c": close,
        "v": volume,
        "n": 100,
        "vw": Decimal("102.2"),
    }


def parse(
    bars: list[dict[str, object]],
    *,
    observed_at=NOW,
    token: object = None,
):
    return AlpacaStockBarsParser().parse_page(
        {"bars": bars, "symbol": "AAPL", "next_page_token": token},
        fetch_request(),
        observed_at,
    )


def test_rfc3339_utc_is_mapped_to_new_york_session_across_dst() -> None:
    page = parse(
        [
            row("2026-01-15T05:00:00Z"),
            row("2026-07-17T04:00:00Z"),
        ]
    )

    assert [bar.session_date.serialize() for bar in page.bars] == [
        "2026-01-15",
        "2026-07-17",
    ]


def test_split_adjusted_volume_is_preserved_and_identity_is_deterministic() -> None:
    parser = AlpacaStockBarsParser()
    request = fetch_request()
    body = {"bars": [row()], "symbol": "AAPL", "next_page_token": None}

    first = parser.parse_page(body, request, NOW).bars[0]
    later = parser.parse_page(body, request, NOW + timedelta(hours=1)).bars[0]

    assert first.volume == 1000
    assert first.source_record_key == "XNGS.AAPL.20260717.IEX.SPLIT"
    assert first.source_version == later.source_version
    assert first.available_at != later.available_at


def test_content_change_creates_new_immutable_source_version() -> None:
    first_body = {"bars": [row()], "symbol": "AAPL", "next_page_token": None}
    revised = deepcopy(first_body)
    revised["bars"][0]["c"] = Decimal("103.5")  # type: ignore[index]
    parser = AlpacaStockBarsParser()

    first = parser.parse_page(first_body, fetch_request(), NOW).bars[0]
    changed = parser.parse_page(revised, fetch_request(), NOW).bars[0]

    assert first.source_record_key == changed.source_record_key
    assert first.source_version != changed.source_version


@pytest.mark.parametrize(
    "changed",
    (
        {"c": 102.5},
        {"c": True},
        {"v": True},
        {"v": -1},
        {"n": -1},
        {"vw": "102.2"},
        {"t": "not-rfc3339"},
        {"t": "2026-07-17T05:00:00+01:00"},
        {"h": Decimal("100")},
    ),
)
def test_invalid_schema_or_values_are_rejected(changed: dict[str, object]) -> None:
    value = row()
    value.update(changed)

    with pytest.raises(AlpacaProviderError) as raised:
        parse([value])

    assert raised.value.category in {
        AlpacaErrorCategory.RESPONSE_VALUE_INVALID,
        AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID,
    }


def test_cutoff_filter_sort_duplicate_and_page_token_contract() -> None:
    page = parse(
        [
            row("2026-07-18T04:00:00Z"),
            row("2026-07-16T04:00:00Z"),
            row("2026-07-15T04:00:00Z"),
        ],
        token="opaque",
    )
    assert [bar.session_date.serialize() for bar in page.bars] == [
        "2026-07-15",
        "2026-07-16",
    ]
    assert page.next_page_token == "opaque"

    with pytest.raises(AlpacaProviderError) as duplicate:
        parse([row(), row()])
    assert duplicate.value.category is AlpacaErrorCategory.RESPONSE_VALUE_INVALID

    with pytest.raises(AlpacaProviderError) as bad_token:
        parse([], token=1)
    assert bad_token.value.category is AlpacaErrorCategory.PAGINATION_INVALID


def test_symbol_mismatch_and_malformed_response_are_rejected() -> None:
    parser = AlpacaStockBarsParser()
    request = fetch_request()
    with pytest.raises(AlpacaProviderError) as symbol:
        parser.parse_page(
            {"bars": [row()], "symbol": "MSFT", "next_page_token": None},
            request,
            NOW,
        )
    assert symbol.value.category is AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID

    for malformed in (None, [], {"bars": None, "symbol": "AAPL"}):
        with pytest.raises(AlpacaProviderError) as raised:
            parser.parse_page(malformed, request, NOW)
        assert raised.value.category is AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID
