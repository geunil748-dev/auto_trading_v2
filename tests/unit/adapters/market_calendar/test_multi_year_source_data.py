import re
from datetime import date

from auto_trading_v2.adapters.market_calendar.data import (
    ANNUAL_SCHEDULES,
    OFFICIAL_SOURCES,
    SOURCE_MANIFEST_DIGEST,
)

EXPECTED_COUNTS = {
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


def test_source_manifest_has_exact_identity_coverage_and_digest() -> None:
    assert SOURCE_MANIFEST_DIGEST == (
        "1af97a32a7a0db2b441839c37017580937d42cdbeb92e032997b3087951f2ff3"
    )
    assert [value.year for value in ANNUAL_SCHEDULES] == list(range(2018, 2027))
    assert ANNUAL_SCHEDULES[0].coverage_start == date(2018, 1, 1)
    assert ANNUAL_SCHEDULES[-1].coverage_end == date(2026, 12, 31)
    assert {value.year: value.expected_session_count for value in ANNUAL_SCHEDULES} == (
        EXPECTED_COUNTS
    )


def test_each_year_has_safe_nonoverlapping_exception_data_and_official_sources() -> None:
    known_sources = {value.code for value in OFFICIAL_SOURCES}
    assert len(known_sources) == len(OFFICIAL_SOURCES)
    for schedule in ANNUAL_SCHEDULES:
        closures = [day for day, _reason in schedule.closures]
        early_closes = [day for day, _reason, _close in schedule.early_closes]
        reasons = [reason for _day, reason in schedule.closures]
        reasons += [reason for _day, reason, _close in schedule.early_closes]
        assert len(closures) == len(set(closures))
        assert len(early_closes) == len(set(early_closes))
        assert set(closures).isdisjoint(early_closes)
        assert all(day.year == schedule.year for day in closures + early_closes)
        assert all(re.fullmatch(r"[A-Z0-9_]{1,96}", reason) for reason in reasons)
        assert set(schedule.source_codes) <= known_sources
        assert any(code.startswith("NYSE_") for code in schedule.source_codes)
        assert any(code.startswith("NASDAQ_") for code in schedule.source_codes)
        assert schedule.verified_at == date(2026, 8, 4)


def test_exceptional_closures_are_exactly_the_two_official_mourning_dates() -> None:
    exceptional = {
        day: reason
        for schedule in ANNUAL_SCHEDULES
        for day, reason in schedule.closures
        if reason.startswith("NATIONAL_DAY_OF_MOURNING")
    }

    assert exceptional == {
        date(2018, 12, 5): "NATIONAL_DAY_OF_MOURNING_GHW_BUSH",
        date(2025, 1, 9): "NATIONAL_DAY_OF_MOURNING_JIMMY_CARTER",
    }
