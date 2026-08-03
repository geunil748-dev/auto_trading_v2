"""Immutable contracts for the daily technical feature calculation and service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.application.feature_building.errors import (
    DailyTechnicalFeatureBuildError,
)
from auto_trading_v2.domain.errors import ValidationError
from auto_trading_v2.domain.feature_snapshots import (
    FeatureSnapshot,
    FeatureSnapshotInput,
    TradingDayHorizon,
)
from auto_trading_v2.domain.primitives import Symbol
from auto_trading_v2.domain.primitives.time import normalize_utc

FEATURE_SET_CODE = "US_EQUITY_DAILY_TECHNICAL"
FEATURE_SET_VERSION = "v1"
PRICE_ONLY_FEATURE_SET_CODE = FEATURE_SET_CODE
PRICE_ONLY_FEATURE_SET_VERSION = "v2"
INSUFFICIENT_REASON = "INSUFFICIENT_COMPLETED_DAILY_BARS"
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class DailyTechnicalCalculationOutcome(StrEnum):
    SNAPSHOT_READY = "SNAPSHOT_READY"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class DailyTechnicalCalculationResult:
    outcome: DailyTechnicalCalculationOutcome
    snapshot_input: FeatureSnapshotInput | None
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BuildDailyTechnicalFeatureSnapshotCommand:
    source_code: str
    symbol: Symbol
    as_of: datetime
    horizon: TradingDayHorizon

    def __post_init__(self) -> None:
        if not isinstance(self.source_code, str):
            raise DailyTechnicalFeatureBuildError("source_code 타입이 올바르지 않습니다.")
        source_code = self.source_code.strip()
        if not _CODE_PATTERN.fullmatch(source_code):
            raise DailyTechnicalFeatureBuildError("source_code 형식이 올바르지 않습니다.")
        if not isinstance(self.symbol, Symbol):
            raise DailyTechnicalFeatureBuildError("symbol 타입이 올바르지 않습니다.")
        if not isinstance(self.horizon, TradingDayHorizon):
            raise DailyTechnicalFeatureBuildError("horizon 타입이 올바르지 않습니다.")
        try:
            as_of = normalize_utc(self.as_of)
        except ValidationError:
            raise DailyTechnicalFeatureBuildError(
                "as_of는 timezone-aware datetime이어야 합니다."
            ) from None
        object.__setattr__(self, "source_code", source_code)
        object.__setattr__(self, "as_of", as_of)


@dataclass(frozen=True, slots=True)
class BuildDailyPriceTechnicalFeatureSnapshotCommand:
    """Explicit request for the price-only daily technical FeatureSet v2."""

    source_code: str
    symbol: Symbol
    as_of: datetime
    horizon: TradingDayHorizon

    def __post_init__(self) -> None:
        validated = BuildDailyTechnicalFeatureSnapshotCommand(
            self.source_code,
            self.symbol,
            self.as_of,
            self.horizon,
        )
        object.__setattr__(self, "source_code", validated.source_code)
        object.__setattr__(self, "as_of", validated.as_of)


class DailyTechnicalFeatureSnapshotBuildOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class DailyTechnicalFeatureSnapshotBuildResult:
    outcome: DailyTechnicalFeatureSnapshotBuildOutcome
    snapshot: FeatureSnapshot | None
    reason_codes: tuple[str, ...] = ()
