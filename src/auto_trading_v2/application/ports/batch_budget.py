"""Provider-neutral batch budget and provider-role boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class DailyMarketDataProviderRole(StrEnum):
    PRIMARY_FEATURE_SOURCE = "PRIMARY_FEATURE_SOURCE"
    VALIDATION_ONLY = "VALIDATION_ONLY"
    EXPERIMENTAL = "EXPERIMENTAL"


@dataclass(frozen=True, slots=True)
class DailyMarketDataBatchBudgetAssessment:
    provider_code: str
    estimated_credits: int | None
    available_daily_credits: int | None
    available_minute_credits: int | None
    budget_known: bool
    can_start: bool


class DailyMarketDataBatchBudgetPort(Protocol):
    @property
    def provider_code(self) -> str: ...

    @property
    def provider_role(self) -> DailyMarketDataProviderRole: ...

    @property
    def enabled(self) -> bool: ...

    @property
    def configured(self) -> bool: ...

    @property
    def maximum_rows_per_request(self) -> int | None: ...

    def estimate_maximum_cost(
        self,
        member_count: int,
        requested_session_count: int,
    ) -> int | None: ...

    def available_daily_budget(self) -> int | None: ...

    def available_minute_budget(self) -> int | None: ...

    def consumed_daily_credits(self) -> int | None: ...
