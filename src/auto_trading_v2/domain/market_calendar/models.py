"""Provider-neutral US equity core-session calendar domain."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from auto_trading_v2.domain.market_calendar.errors import (
    MarketCalendarValidationError,
)
from auto_trading_v2.domain.primitives import SessionDate
from auto_trading_v2.domain.primitives.time import normalize_utc

_NEW_YORK = ZoneInfo("America/New_York")
_REASON_CODE = re.compile(r"^[A-Z0-9_]{1,96}$")
_MIC_FAMILIES = {
    "XNGS": "NASDAQ_CORE",
    "XNGM": "NASDAQ_CORE",
    "XNCM": "NASDAQ_CORE",
    "XNYS": "NYSE_CORE",
    "XASE": "NYSE_CORE",
}


class ExchangeCalendarCode(StrEnum):
    US_EQUITY_CORE = "US_EQUITY_CORE"


class ExchangeCalendarVersion(StrEnum):
    V2026_1 = "2026.v1"


class ExchangeCalendarFamily(StrEnum):
    NASDAQ_CORE = "NASDAQ_CORE"
    NYSE_CORE = "NYSE_CORE"


class MarketSessionKind(StrEnum):
    REGULAR = "REGULAR"
    EARLY_CLOSE = "EARLY_CLOSE"


class CompletedSessionResolutionOutcome(StrEnum):
    RESOLVED = "RESOLVED"
    NO_COMPLETED_SESSION = "NO_COMPLETED_SESSION"
    CALENDAR_OUT_OF_COVERAGE = "CALENDAR_OUT_OF_COVERAGE"
    UNSUPPORTED_MIC = "UNSUPPORTED_MIC"


class ProviderBarCalendarErrorCategory(StrEnum):
    ON_NON_TRADING_DAY = "PROVIDER_BAR_ON_NON_TRADING_DAY"
    AFTER_COMPLETED_CUTOFF = "PROVIDER_BAR_AFTER_COMPLETED_CUTOFF"
    OUT_OF_CALENDAR_COVERAGE = "PROVIDER_BAR_OUT_OF_CALENDAR_COVERAGE"
    DUPLICATE_SESSION = "PROVIDER_BAR_DUPLICATE_SESSION"
    UNSUPPORTED_MIC = "PROVIDER_BAR_UNSUPPORTED_MIC"
    SEQUENCE_INCONSISTENT = "PROVIDER_BAR_SEQUENCE_INCONSISTENT"


def supported_mic_codes() -> tuple[str, ...]:
    return tuple(_MIC_FAMILIES)


def calendar_family_for_mic(value: object) -> ExchangeCalendarFamily | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    family = _MIC_FAMILIES.get(normalized)
    return None if family is None else ExchangeCalendarFamily(family)


def normalize_supported_mic(value: object) -> str:
    if not isinstance(value, str):
        raise MarketCalendarValidationError("MIC는 문자열이어야 합니다.")
    normalized = value.strip().upper()
    if calendar_family_for_mic(normalized) is None:
        raise MarketCalendarValidationError("지원하지 않는 미국 listing MIC입니다.")
    return normalized


@dataclass(frozen=True, slots=True)
class CalendarCoverage:
    start: date
    end: date

    def __post_init__(self) -> None:
        if type(self.start) is not date or type(self.end) is not date:
            raise MarketCalendarValidationError("calendar coverage는 date여야 합니다.")
        if self.start > self.end:
            raise MarketCalendarValidationError("calendar coverage 범위가 올바르지 않습니다.")

    def contains(self, value: date) -> bool:
        return type(value) is date and self.start <= value <= self.end


@dataclass(frozen=True, slots=True)
class MarketCalendarMetadata:
    calendar_code: ExchangeCalendarCode
    calendar_version: ExchangeCalendarVersion
    coverage: CalendarCoverage
    timezone_name: str
    source_codes: tuple[str, ...]
    verified_at: date

    def __post_init__(self) -> None:
        if self.timezone_name != "America/New_York":
            raise MarketCalendarValidationError("calendar timezone이 올바르지 않습니다.")
        if not self.source_codes or any(
            not _REASON_CODE.fullmatch(value) for value in self.source_codes
        ):
            raise MarketCalendarValidationError("calendar source code가 올바르지 않습니다.")
        if type(self.verified_at) is not date:
            raise MarketCalendarValidationError("verified_at은 date여야 합니다.")


@dataclass(frozen=True, slots=True)
class CompletionGracePeriod:
    value: timedelta

    def __post_init__(self) -> None:
        if type(self.value) is not timedelta:
            raise MarketCalendarValidationError("completion grace는 timedelta여야 합니다.")
        if self.value < timedelta(0) or self.value > timedelta(hours=24):
            raise MarketCalendarValidationError("completion grace는 0~24시간이어야 합니다.")


@dataclass(frozen=True, slots=True)
class MarketSession:
    calendar_code: ExchangeCalendarCode
    calendar_version: ExchangeCalendarVersion
    calendar_family: ExchangeCalendarFamily
    mic_code: str
    session_date: SessionDate
    open_at: datetime
    close_at: datetime
    session_kind: MarketSessionKind
    reason_code: str | None = None

    def __post_init__(self) -> None:
        mic_code = normalize_supported_mic(self.mic_code)
        if calendar_family_for_mic(mic_code) is not self.calendar_family:
            raise MarketCalendarValidationError("MIC와 calendar family가 일치하지 않습니다.")
        if not isinstance(self.session_date, SessionDate):
            raise MarketCalendarValidationError("session_date 타입이 올바르지 않습니다.")
        try:
            open_at = normalize_utc(self.open_at)
            close_at = normalize_utc(self.close_at)
        except Exception:
            raise MarketCalendarValidationError(
                "session open/close에는 시간대 정보가 필요합니다."
            ) from None
        if open_at >= close_at:
            raise MarketCalendarValidationError("session open은 close보다 이전이어야 합니다.")
        local_open = open_at.astimezone(_NEW_YORK)
        local_close = close_at.astimezone(_NEW_YORK)
        expected_close = (
            time(13) if self.session_kind is MarketSessionKind.EARLY_CLOSE else time(16)
        )
        if (
            local_open.date() != self.session_date.value
            or local_close.date() != self.session_date.value
            or local_open.time().replace(tzinfo=None) != time(9, 30)
            or local_close.time().replace(tzinfo=None) != expected_close
        ):
            raise MarketCalendarValidationError("core session 시간이 올바르지 않습니다.")
        if self.session_kind is MarketSessionKind.EARLY_CLOSE:
            if self.reason_code is None or not _REASON_CODE.fullmatch(self.reason_code):
                raise MarketCalendarValidationError("조기 종료 reason code가 필요합니다.")
        elif self.reason_code is not None:
            raise MarketCalendarValidationError("정규 session에는 reason code를 둘 수 없습니다.")
        object.__setattr__(self, "mic_code", mic_code)
        object.__setattr__(self, "open_at", open_at)
        object.__setattr__(self, "close_at", close_at)


@dataclass(frozen=True, slots=True)
class CompletedSessionResolution:
    outcome: CompletedSessionResolutionOutcome
    as_of: datetime
    calendar_code: ExchangeCalendarCode
    calendar_version: ExchangeCalendarVersion
    session: MarketSession | None = None
    eligible_at: datetime | None = None
    previous_session_date: SessionDate | None = None

    def __post_init__(self) -> None:
        try:
            as_of = normalize_utc(self.as_of)
        except Exception:
            raise MarketCalendarValidationError("as_of에는 시간대 정보가 필요합니다.") from None
        object.__setattr__(self, "as_of", as_of)
        if self.outcome is CompletedSessionResolutionOutcome.RESOLVED:
            if self.session is None or self.eligible_at is None:
                raise MarketCalendarValidationError("resolved session metadata가 필요합니다.")
            try:
                eligible_at = normalize_utc(self.eligible_at)
            except Exception:
                raise MarketCalendarValidationError("eligible_at이 올바르지 않습니다.") from None
            if eligible_at < self.session.close_at or as_of < eligible_at:
                raise MarketCalendarValidationError("완료 session 시각 관계가 올바르지 않습니다.")
            object.__setattr__(self, "eligible_at", eligible_at)
        elif any(
            value is not None
            for value in (self.session, self.eligible_at, self.previous_session_date)
        ):
            raise MarketCalendarValidationError("미해결 결과에는 session metadata가 없습니다.")
