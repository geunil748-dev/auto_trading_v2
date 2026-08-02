"""Safe canonical identities for the exact future-bar revisions used."""

import re
from dataclasses import dataclass
from datetime import datetime

from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_outcomes.errors import (
    OutcomeObservationValidationError,
)
from auto_trading_v2.domain.primitives import DailyMarketBarID, SessionDate
from auto_trading_v2.domain.primitives.time import UtcTimestamp, normalize_utc

_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class FutureBarProvenanceEntry:
    daily_market_bar_id: DailyMarketBarID
    session_date: SessionDate
    source_code: str
    source_record_key: str
    source_version: str
    available_at: datetime
    content_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.daily_market_bar_id, DailyMarketBarID):
            _invalid("FUTURE_BAR_PROVENANCE_ID_INVALID")
        if not isinstance(self.session_date, SessionDate):
            _invalid("FUTURE_BAR_PROVENANCE_SESSION_INVALID")
        for value in (self.source_code, self.source_record_key, self.source_version):
            if not isinstance(value, str) or not _CODE.fullmatch(value):
                _invalid("FUTURE_BAR_PROVENANCE_SOURCE_INVALID")
        if not isinstance(self.content_digest, str) or not _DIGEST.fullmatch(self.content_digest):
            _invalid("FUTURE_BAR_PROVENANCE_DIGEST_INVALID")
        try:
            available = normalize_utc(self.available_at)
        except (TypeError, ValidationError):
            _invalid("FUTURE_BAR_PROVENANCE_AVAILABLE_AT_INVALID")
        object.__setattr__(self, "available_at", available)

    def as_json(self) -> dict[str, object]:
        return {
            "available_at": UtcTimestamp(self.available_at).serialize(),
            "content_digest": self.content_digest,
            "daily_market_bar_id": self.daily_market_bar_id.serialize(),
            "session_date": self.session_date.serialize(),
            "source_code": self.source_code,
            "source_record_key": self.source_record_key,
            "source_version": self.source_version,
        }


def canonical_future_bar_provenance(
    entries: tuple[FutureBarProvenanceEntry, ...],
) -> tuple[FutureBarProvenanceEntry, ...]:
    if not entries or any(not isinstance(entry, FutureBarProvenanceEntry) for entry in entries):
        _invalid("FUTURE_BAR_PROVENANCE_INVALID")
    ordered = tuple(sorted(entries, key=lambda entry: entry.session_date.value))
    if len({entry.session_date for entry in ordered}) != len(ordered):
        _invalid("FUTURE_BAR_PROVENANCE_DUPLICATE_SESSION")
    return ordered


def _invalid(category: str) -> None:
    raise OutcomeObservationValidationError(category)
