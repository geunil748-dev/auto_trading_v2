"""Verified official US equity core-session exceptions for 2018 through 2026."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, time

from auto_trading_v2.adapters.market_calendar.data.sources import OFFICIAL_SOURCES


@dataclass(frozen=True, slots=True)
class AnnualOfficialSchedule:
    year: int
    coverage_start: date
    coverage_end: date
    closures: tuple[tuple[date, str], ...]
    early_closes: tuple[tuple[date, str, time], ...]
    source_codes: tuple[str, ...]
    verified_at: date
    expected_session_count: int


def _d(value: str) -> date:
    return date.fromisoformat(value)


def _closures(*values: tuple[str, str]) -> tuple[tuple[date, str], ...]:
    return tuple((_d(value), reason) for value, reason in values)


def _early(*values: tuple[str, str]) -> tuple[tuple[date, str, time], ...]:
    return tuple((_d(value), reason, time(13)) for value, reason in values)


_VERIFIED_AT = date(2026, 8, 4)
_COMMON = {
    2018: _closures(
        ("2018-01-01", "NEW_YEARS_DAY"),
        ("2018-01-15", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2018-02-19", "WASHINGTONS_BIRTHDAY"),
        ("2018-03-30", "GOOD_FRIDAY"),
        ("2018-05-28", "MEMORIAL_DAY"),
        ("2018-07-04", "INDEPENDENCE_DAY"),
        ("2018-09-03", "LABOR_DAY"),
        ("2018-11-22", "THANKSGIVING_DAY"),
        ("2018-12-05", "NATIONAL_DAY_OF_MOURNING_GHW_BUSH"),
        ("2018-12-25", "CHRISTMAS_DAY"),
    ),
    2019: _closures(
        ("2019-01-01", "NEW_YEARS_DAY"),
        ("2019-01-21", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2019-02-18", "WASHINGTONS_BIRTHDAY"),
        ("2019-04-19", "GOOD_FRIDAY"),
        ("2019-05-27", "MEMORIAL_DAY"),
        ("2019-07-04", "INDEPENDENCE_DAY"),
        ("2019-09-02", "LABOR_DAY"),
        ("2019-11-28", "THANKSGIVING_DAY"),
        ("2019-12-25", "CHRISTMAS_DAY"),
    ),
    2020: _closures(
        ("2020-01-01", "NEW_YEARS_DAY"),
        ("2020-01-20", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2020-02-17", "WASHINGTONS_BIRTHDAY"),
        ("2020-04-10", "GOOD_FRIDAY"),
        ("2020-05-25", "MEMORIAL_DAY"),
        ("2020-07-03", "INDEPENDENCE_DAY_OBSERVED"),
        ("2020-09-07", "LABOR_DAY"),
        ("2020-11-26", "THANKSGIVING_DAY"),
        ("2020-12-25", "CHRISTMAS_DAY"),
    ),
    2021: _closures(
        ("2021-01-01", "NEW_YEARS_DAY"),
        ("2021-01-18", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2021-02-15", "WASHINGTONS_BIRTHDAY"),
        ("2021-04-02", "GOOD_FRIDAY"),
        ("2021-05-31", "MEMORIAL_DAY"),
        ("2021-07-05", "INDEPENDENCE_DAY_OBSERVED"),
        ("2021-09-06", "LABOR_DAY"),
        ("2021-11-25", "THANKSGIVING_DAY"),
        ("2021-12-24", "CHRISTMAS_DAY_OBSERVED"),
    ),
    2022: _closures(
        ("2022-01-17", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2022-02-21", "WASHINGTONS_BIRTHDAY"),
        ("2022-04-15", "GOOD_FRIDAY"),
        ("2022-05-30", "MEMORIAL_DAY"),
        ("2022-06-20", "JUNETEENTH_OBSERVED"),
        ("2022-07-04", "INDEPENDENCE_DAY"),
        ("2022-09-05", "LABOR_DAY"),
        ("2022-11-24", "THANKSGIVING_DAY"),
        ("2022-12-26", "CHRISTMAS_DAY_OBSERVED"),
    ),
    2023: _closures(
        ("2023-01-02", "NEW_YEARS_DAY_OBSERVED"),
        ("2023-01-16", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2023-02-20", "WASHINGTONS_BIRTHDAY"),
        ("2023-04-07", "GOOD_FRIDAY"),
        ("2023-05-29", "MEMORIAL_DAY"),
        ("2023-06-19", "JUNETEENTH"),
        ("2023-07-04", "INDEPENDENCE_DAY"),
        ("2023-09-04", "LABOR_DAY"),
        ("2023-11-23", "THANKSGIVING_DAY"),
        ("2023-12-25", "CHRISTMAS_DAY"),
    ),
    2024: _closures(
        ("2024-01-01", "NEW_YEARS_DAY"),
        ("2024-01-15", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2024-02-19", "WASHINGTONS_BIRTHDAY"),
        ("2024-03-29", "GOOD_FRIDAY"),
        ("2024-05-27", "MEMORIAL_DAY"),
        ("2024-06-19", "JUNETEENTH"),
        ("2024-07-04", "INDEPENDENCE_DAY"),
        ("2024-09-02", "LABOR_DAY"),
        ("2024-11-28", "THANKSGIVING_DAY"),
        ("2024-12-25", "CHRISTMAS_DAY"),
    ),
    2025: _closures(
        ("2025-01-01", "NEW_YEARS_DAY"),
        ("2025-01-09", "NATIONAL_DAY_OF_MOURNING_JIMMY_CARTER"),
        ("2025-01-20", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2025-02-17", "WASHINGTONS_BIRTHDAY"),
        ("2025-04-18", "GOOD_FRIDAY"),
        ("2025-05-26", "MEMORIAL_DAY"),
        ("2025-06-19", "JUNETEENTH"),
        ("2025-07-04", "INDEPENDENCE_DAY"),
        ("2025-09-01", "LABOR_DAY"),
        ("2025-11-27", "THANKSGIVING_DAY"),
        ("2025-12-25", "CHRISTMAS_DAY"),
    ),
    2026: _closures(
        ("2026-01-01", "NEW_YEARS_DAY"),
        ("2026-01-19", "MARTIN_LUTHER_KING_JR_DAY"),
        ("2026-02-16", "WASHINGTONS_BIRTHDAY"),
        ("2026-04-03", "GOOD_FRIDAY"),
        ("2026-05-25", "MEMORIAL_DAY"),
        ("2026-06-19", "JUNETEENTH"),
        ("2026-07-03", "INDEPENDENCE_DAY_OBSERVED"),
        ("2026-09-07", "LABOR_DAY"),
        ("2026-11-26", "THANKSGIVING_DAY"),
        ("2026-12-25", "CHRISTMAS_DAY"),
    ),
}
_EARLY = {
    2018: _early(
        ("2018-07-03", "INDEPENDENCE_DAY_EVE"),
        ("2018-11-23", "DAY_AFTER_THANKSGIVING"),
        ("2018-12-24", "CHRISTMAS_EVE"),
    ),
    2019: _early(
        ("2019-07-03", "INDEPENDENCE_DAY_EVE"),
        ("2019-11-29", "DAY_AFTER_THANKSGIVING"),
        ("2019-12-24", "CHRISTMAS_EVE"),
    ),
    2020: _early(("2020-11-27", "DAY_AFTER_THANKSGIVING"), ("2020-12-24", "CHRISTMAS_EVE")),
    2021: _early(("2021-11-26", "DAY_AFTER_THANKSGIVING")),
    2022: _early(("2022-11-25", "DAY_AFTER_THANKSGIVING")),
    2023: _early(("2023-07-03", "INDEPENDENCE_DAY_EVE"), ("2023-11-24", "DAY_AFTER_THANKSGIVING")),
    2024: _early(
        ("2024-07-03", "INDEPENDENCE_DAY_EVE"),
        ("2024-11-29", "DAY_AFTER_THANKSGIVING"),
        ("2024-12-24", "CHRISTMAS_EVE"),
    ),
    2025: _early(
        ("2025-07-03", "INDEPENDENCE_DAY_EVE"),
        ("2025-11-28", "DAY_AFTER_THANKSGIVING"),
        ("2025-12-24", "CHRISTMAS_EVE"),
    ),
    2026: _early(("2026-11-27", "DAY_AFTER_THANKSGIVING"), ("2026-12-24", "CHRISTMAS_EVE")),
}
_COUNTS = {
    2018: 251,
    2019: 252,
    2020: 253,
    2021: 252,
    2022: 251,
    2023: 250,
    2024: 252,
    2025: 250,
    2026: 251,
}


def _sources(year: int) -> tuple[str, ...]:
    nyse = (
        "NYSE_2018_2020_CALENDAR"
        if year <= 2020
        else "NYSE_2021_2023_CALENDAR"
        if year <= 2022
        else "NYSE_2022_2024_CALENDAR"
        if year == 2023
        else "NYSE_2023_2025_CALENDAR"
        if year <= 2025
        else "NYSE_2026_CALENDAR"
    )
    values = [nyse, f"NASDAQ_{year}_{'ALERTS' if year <= 2020 else 'CALENDAR'}"]
    if year == 2018:
        values += ["NYSE_2018_MOURNING_NOTICE", "NASDAQ_2018_MOURNING_NOTICE"]
    if year == 2025:
        values += ["NYSE_2025_MOURNING_NOTICE", "NASDAQ_2025_MOURNING_NOTICE"]
    return tuple(values)


ANNUAL_SCHEDULES = tuple(
    AnnualOfficialSchedule(
        year,
        date(year, 1, 1),
        date(year, 12, 31),
        _COMMON[year],
        _EARLY[year],
        _sources(year),
        _VERIFIED_AT,
        _COUNTS[year],
    )
    for year in range(2018, 2027)
)


def _manifest_digest() -> str:
    payload = {
        "sources": [(value.code, value.title, value.url) for value in OFFICIAL_SOURCES],
        "years": [
            {
                "year": value.year,
                "coverage": [value.coverage_start.isoformat(), value.coverage_end.isoformat()],
                "closures": [(day.isoformat(), reason) for day, reason in value.closures],
                "early_closes": [
                    (day.isoformat(), reason, close.isoformat())
                    for day, reason, close in value.early_closes
                ],
                "sources": value.source_codes,
                "verified_at": value.verified_at.isoformat(),
                "expected_session_count": value.expected_session_count,
            }
            for value in ANNUAL_SCHEDULES
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


SOURCE_MANIFEST_DIGEST = _manifest_digest()
