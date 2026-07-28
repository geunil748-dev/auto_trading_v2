"""Official Twelve Data /time_series completed-daily adapter."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from auto_trading_v2.adapters.market_data import HttpRequest, HttpResponse, HttpTransport
from auto_trading_v2.adapters.market_data.twelve_data.credit import (
    TwelveDataCreditLimiter,
)
from auto_trading_v2.adapters.market_data.twelve_data.errors import (
    TwelveDataErrorCategory,
    TwelveDataProviderError,
)
from auto_trading_v2.adapters.market_data.twelve_data.parser import (
    TWELVE_DATA_SOURCE_CODE,
    TwelveDataTimeSeriesParser,
)
from auto_trading_v2.application.ports.daily_market_data import (
    CompletedDailyMarketBarObservation,
    DailyMarketDataProviderCapabilities,
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.config.twelve_data import TwelveDataMarketDataSettings
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.ports.clock import Clock

TWELVE_DATA_CAPABILITIES = DailyMarketDataProviderCapabilities(
    provider_code=TWELVE_DATA_SOURCE_CODE,
    official=True,
    requires_api_key=True,
    supports_raw_daily_bars=True,
    supports_split_adjusted_daily_bars=True,
    supports_adjusted_volume=False,
    supports_completed_cutoff=True,
    supports_pagination=True,
    maximum_rows_per_request=5000,
)
_SUPPORTED_MICS = frozenset({"XNAS", "XNYS", "XASE"})
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class TwelveDataDailyMarketDataProvider:
    def __init__(
        self,
        settings: TwelveDataMarketDataSettings,
        transport: HttpTransport,
        credit_limiter: TwelveDataCreditLimiter,
        clock: Clock,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        parser: TwelveDataTimeSeriesParser | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._credit_limiter = credit_limiter
        self._clock = clock
        self._sleeper = sleeper
        self._parser = parser or TwelveDataTimeSeriesParser()

    @property
    def capabilities(self) -> DailyMarketDataProviderCapabilities:
        return TWELVE_DATA_CAPABILITIES

    def fetch_completed_daily_bars(
        self,
        request: FetchCompletedDailyBarsRequest,
    ) -> tuple[CompletedDailyMarketBarObservation, ...]:
        self._validate(request)
        response = self._send_with_retry(self._http_request(request))
        payload = self._payload(response)
        provider_error = _provider_error_category(payload)
        if provider_error is not None:
            raise TwelveDataProviderError(provider_error)
        observed_at = self._clock.now_utc()
        return self._parser.parse(payload, request, observed_at)

    def _validate(self, request: FetchCompletedDailyBarsRequest) -> None:
        if not self._settings.enabled:
            raise TwelveDataProviderError(TwelveDataErrorCategory.PROVIDER_DISABLED)
        if self._settings.api_key is None:
            raise TwelveDataProviderError(TwelveDataErrorCategory.CONFIGURATION_MISSING)
        if request.source_code != TWELVE_DATA_SOURCE_CODE:
            raise TwelveDataProviderError(TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST)
        if request.mic_code not in _SUPPORTED_MICS:
            raise TwelveDataProviderError(TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST)
        if request.completed_through_session_date is None:
            raise TwelveDataProviderError(TwelveDataErrorCategory.CONFIGURATION_INVALID)
        maximum = TWELVE_DATA_CAPABILITIES.maximum_rows_per_request
        if maximum is not None and request.requested_session_count > maximum:
            raise TwelveDataProviderError(TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST)
        if request.adjustment_basis not in {
            DailyMarketBarAdjustmentBasis.RAW,
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        }:
            raise TwelveDataProviderError(TwelveDataErrorCategory.ADJUSTMENT_UNSUPPORTED)

    def _http_request(self, request: FetchCompletedDailyBarsRequest) -> HttpRequest:
        api_key = self._settings.api_key
        cutoff = request.completed_through_session_date
        if api_key is None or cutoff is None or request.mic_code is None:
            raise TwelveDataProviderError(TwelveDataErrorCategory.CONFIGURATION_MISSING)
        adjustment = (
            "splits"
            if request.adjustment_basis is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
            else "none"
        )
        return HttpRequest(
            method="GET",
            path="/time_series",
            query=(
                ("symbol", request.symbol.value),
                ("mic_code", request.mic_code),
                ("interval", "1day"),
                ("outputsize", str(request.requested_session_count)),
                ("end_date", cutoff.serialize()),
                ("adjust", adjustment),
                ("order", "asc"),
                ("apikey", api_key.reveal()),
            ),
        )

    def _send_with_retry(self, request: HttpRequest) -> HttpResponse:
        maximum = self._settings.maximum_retry_attempts
        last_category = TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
        for attempt in range(1, maximum + 1):
            self._credit_limiter.acquire(1)
            try:
                response = self._transport.send(
                    self._settings.base_url,
                    request,
                    connect_timeout_seconds=self._settings.connect_timeout_seconds,
                    read_timeout_seconds=self._settings.read_timeout_seconds,
                )
            except TimeoutError:
                last_category = TwelveDataErrorCategory.HTTP_TIMEOUT
            except OSError:
                last_category = TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
            else:
                if response.status_code not in _RETRYABLE_STATUS:
                    if response.status_code in {401, 403}:
                        raise TwelveDataProviderError(
                            TwelveDataErrorCategory.AUTHENTICATION_REJECTED
                        )
                    if response.status_code >= 400:
                        raise TwelveDataProviderError(
                            TwelveDataErrorCategory.HTTP_PERMANENT_FAILURE
                        )
                    provider_error = _provider_error_category(self._payload(response))
                    if provider_error is None:
                        return response
                    if provider_error not in {
                        TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT,
                        TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE,
                    }:
                        raise TwelveDataProviderError(provider_error)
                    last_category = provider_error
                else:
                    last_category = (
                        TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT
                        if response.status_code == 429
                        else TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
                    )
            if attempt < maximum:
                self._sleeper(min(8.0, float(2 ** (attempt - 1))))
        raise TwelveDataProviderError(last_category)

    @staticmethod
    def _payload(response: HttpResponse) -> dict[str, Any]:
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID) from None
        if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
            raise TwelveDataProviderError(TwelveDataErrorCategory.RESPONSE_SCHEMA_INVALID)
        return payload


def _provider_error_category(payload: dict[str, Any]) -> TwelveDataErrorCategory | None:
    if payload.get("status") != "error":
        return None
    raw_code = payload.get("code")
    code = int(raw_code) if isinstance(raw_code, str) and raw_code.isdigit() else raw_code
    if code in {401, 403}:
        return TwelveDataErrorCategory.AUTHENTICATION_REJECTED
    if code == 429:
        return TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT
    if isinstance(code, int) and code >= 500:
        return TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
    return TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST
