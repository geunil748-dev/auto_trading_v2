"""Sanitized creation conflicts for immutable DailyMarketBar records."""


class DailyMarketBarConflictError(RuntimeError):
    def __init__(self, bar_key: str) -> None:
        super().__init__(f"동일한 DailyMarketBar identity에 다른 내용이 존재합니다: {bar_key}")


class DailyMarketBarRaceResolutionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("DailyMarketBar 동시성 충돌을 안전하게 확인할 수 없습니다.")
