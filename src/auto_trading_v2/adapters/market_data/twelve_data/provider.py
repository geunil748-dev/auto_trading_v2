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
_SUPPORTED_LISTING_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})
_SAFE_PARAMETER_HINTS = (
    "symbol",
    "mic_code",
    "interval",
    "outputsize",
    "start_date",
    "end_date",
    "adjust",
    "order",
    "apikey",
)


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
        observed_at = self._clock.now_utc()
        return self._parser.parse(payload, request, observed_at)

    def _validate(self, request: FetchCompletedDailyBarsRequest) -> None:
        if not self._settings.enabled:
            raise TwelveDataProviderError(TwelveDataErrorCategory.PROVIDER_DISABLED)
        if self._settings.api_key is None:
            raise TwelveDataProviderError(TwelveDataErrorCategory.CONFIGURATION_MISSING)
        if request.source_code != TWELVE_DATA_SOURCE_CODE:
            raise TwelveDataProviderError(TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST)
        if request.mic_code not in _SUPPORTED_LISTING_MICS:
            raise TwelveDataProviderError(
                TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST,
                safe_parameter_hint="mic_code",
            )
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
            ),
            headers=(("Authorization", f"apikey {api_key.reveal()}"),),
        )

    def _send_with_retry(self, request: HttpRequest) -> HttpResponse:
        maximum = self._settings.maximum_retry_attempts
        last_category = TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
        last_http_status: int | None = None
        last_provider_code: int | None = None
        last_parameter_hint: str | None = None
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
                last_http_status = None
                last_provider_code = None
                last_parameter_hint = None
            except OSError:
                last_category = TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
                last_http_status = None
                last_provider_code = None
                last_parameter_hint = None
            else:
                provider_code, parameter_hint = _provider_error_metadata(response)
                category = _http_error_category(response.status_code)
                if category is None:
                    payload = self._payload(response)
                    category = _provider_error_category(payload)
                    if category is None:
                        return response
                if category not in {
                    TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT,
                    TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE,
                }:
                    raise TwelveDataProviderError(
                        category,
                        http_status=response.status_code,
                        provider_code=provider_code,
                        safe_parameter_hint=parameter_hint,
                    )
                last_category = category
                last_http_status = response.status_code
                last_provider_code = provider_code
                last_parameter_hint = parameter_hint
            if attempt < maximum:
                self._sleeper(min(8.0, float(2 ** (attempt - 1))))
        raise TwelveDataProviderError(
            last_category,
            http_status=last_http_status,
            provider_code=last_provider_code,
            safe_parameter_hint=last_parameter_hint,
        )

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
    code = _safe_provider_code(payload.get("code"))
    if code == 401:
        return TwelveDataErrorCategory.AUTHENTICATION_REJECTED
    if code == 403:
        return TwelveDataErrorCategory.ACCESS_FORBIDDEN
    if code == 404:
        return TwelveDataErrorCategory.INSTRUMENT_NOT_FOUND
    if code == 429:
        return TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT
    if code is not None and 500 <= code <= 599:
        return TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
    return TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST


def _http_error_category(status_code: int) -> TwelveDataErrorCategory | None:
    if status_code < 400:
        return None
    if status_code == 400:
        return TwelveDataErrorCategory.PROVIDER_REJECTED_REQUEST
    if status_code == 401:
        return TwelveDataErrorCategory.AUTHENTICATION_REJECTED
    if status_code == 403:
        return TwelveDataErrorCategory.ACCESS_FORBIDDEN
    if status_code == 404:
        return TwelveDataErrorCategory.INSTRUMENT_NOT_FOUND
    if status_code == 429:
        return TwelveDataErrorCategory.MINUTE_CREDIT_LIMIT
    if 500 <= status_code <= 599:
        return TwelveDataErrorCategory.HTTP_TRANSIENT_FAILURE
    return TwelveDataErrorCategory.HTTP_PERMANENT_FAILURE


def _provider_error_metadata(response: HttpResponse) -> tuple[int | None, str | None]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    return (
        _safe_provider_code(payload.get("code")),
        _provider_parameter_hint(payload),
    )


def _safe_provider_code(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _provider_parameter_hint(payload: dict[object, object]) -> str | None:
    candidate = payload.get("parameter")
    if isinstance(candidate, str):
        normalized = candidate.strip().lower()
        if normalized in _SAFE_PARAMETER_HINTS:
            return normalized
    message = payload.get("message")
    if not isinstance(message, str):
        return None
    normalized_message = message.lower()
    return next(
        (parameter for parameter in _SAFE_PARAMETER_HINTS if parameter in normalized_message),
        None,
    )
