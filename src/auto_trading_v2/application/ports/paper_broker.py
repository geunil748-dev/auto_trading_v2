"""Paper-broker submission boundary."""

import re
from typing import Protocol

from auto_trading_v2.application.contracts.paper_orders import (
    PaperOrderSubmissionRequest,
    PaperOrderSubmissionResult,
)

_SAFE_CATEGORY = re.compile(r"^[A-Za-z0-9_]{1,64}$")


class PaperBrokerError(RuntimeError):
    """Safe technical failure raised by a PaperBroker adapter."""

    def __init__(self, category: str = "submission_failed") -> None:
        self.category = (
            category
            if isinstance(category, str) and _SAFE_CATEGORY.fullmatch(category)
            else "failure"
        )
        super().__init__(f"paper broker technical failure: {self.category}")


class PaperBroker(Protocol):
    """Submit one validated request without owning persistence."""

    @property
    def broker_code(self) -> str: ...

    def submit(self, request: PaperOrderSubmissionRequest) -> PaperOrderSubmissionResult: ...
