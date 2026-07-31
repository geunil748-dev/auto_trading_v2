"""Official Alpaca single-stock historical daily-bar adapter."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from auto_trading_v2.adapters.market_data import HttpRequest, HttpResponse, HttpTransport
from auto_trading_v2.adapters.market_data.alpaca.errors import (
    AlpacaErrorCategory,
    AlpacaProviderError,
)
from auto_trading_v2.adapters.market_data.alpaca.parser import (
    ALPACA_SOURCE_CODE,
    AlpacaStockBarsParser,
)
from auto_trading_v2.adapters.market_data.alpaca.rate_limit import (
    AlpacaRequestRateLimiter,
)
from auto_trading_v2.application.ports.daily_market_data import (
    CompletedDailyMarketBarObservation,
    DailyMarketDataProviderCapabilities,
    FetchCompletedDailyBarsRequest,
)
from auto_trading_v2.config.alpaca_market_data import AlpacaMarketDataSettings
from auto_trading_v2.domain.daily_market_bars import DailyMarketBarAdjustmentBasis
from auto_trading_v2.ports.clock import Clock

ALPACA_CAPABILITIES = DailyMarketDataProviderCapabilities(
    provider_code=ALPACA_SOURCE_CODE,
    official=True,
    requires_api_key=True,
    supports_raw_daily_bars=True,
    supports_split_adjusted_daily_bars=True,
    supports_adjusted_volume=True,
    supports_completed_cutoff=True,
    supports_pagination=True,
    maximum_rows_per_request=10_000,
)
_SUPPORTED_MICS = frozenset({"XNGS", "XNGM", "XNCM", "XNYS", "XASE"})
_TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})
_SAFE_PARAMETER_HINTS = (
    "timeframe",
    "feed",
    "adjustment",
    "currency",
    "sort",
    "start",
    "end",
    "limit",
    "asof",
    "page_token",
    "symbol",
)


class AlpacaDailyMarketDataProvider:
    def __init__(
        self,
        settings: AlpacaMarketDataSettings,
        transport: HttpTransport,
        rate_limiter: AlpacaRequestRateLimiter,
        clock: Clock,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        parser: AlpacaStockBarsParser | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._rate_limiter = rate_limiter
        self._clock = clock
        self._sleeper = sleeper
        self._parser = parser or AlpacaStockBarsParser()

    @property
    def capabilities(self) -> DailyMarketDataProviderCapabilities:
        return ALPACA_CAPABILITIES

    def fetch_completed_daily_bars(
        self,
        request: FetchCompletedDailyBarsRequest,
    ) -> tuple[CompletedDailyMarketBarObservation, ...]:
        self._validate(request)
        observed_at = self._clock.now_utc()
        token: str | None = None
        seen_tokens: set[str] = set()
        by_session: dict[date, CompletedDailyMarketBarObservation] = {}
        for page_number in range(1, self._settings.maximum_pages + 1):
            response = self._send_with_retry(self._http_request(request, token))
            page = self._parser.parse_page(self._payload(response), request, observed_at)
            for bar in page.bars:
                session = bar.session_date.value
                if session in by_session:
                    raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_VALUE_INVALID)
                by_session[session] = bar
            token = page.next_page_token
            if token is None:
                break
            if token in seen_tokens:
                raise AlpacaProviderError(AlpacaErrorCategory.PAGINATION_INVALID)
            seen_tokens.add(token)
            if page_number == self._settings.maximum_pages:
                raise AlpacaProviderError(AlpacaErrorCategory.PAGINATION_INVALID)
        ordered = sorted(by_session.values(), key=lambda bar: bar.session_date.value)
        return tuple(ordered[-request.requested_session_count :])

    def _validate(self, request: FetchCompletedDailyBarsRequest) -> None:
        if not self._settings.enabled:
            raise AlpacaProviderError(AlpacaErrorCategory.PROVIDER_DISABLED)
        if self._settings.api_key_id is None or self._settings.api_secret_key is None:
            raise AlpacaProviderError(AlpacaErrorCategory.CONFIGURATION_MISSING)
        if request.source_code != ALPACA_SOURCE_CODE:
            raise AlpacaProviderError(AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST)
        if request.mic_code not in _SUPPORTED_MICS:
            raise AlpacaProviderError(
                AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST,
                safe_parameter_hint="unknown",
            )
        if request.completed_through_session_date is None:
            raise AlpacaProviderError(AlpacaErrorCategory.CONFIGURATION_INVALID)
        if request.requested_session_count > 10_000:
            raise AlpacaProviderError(
                AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST,
                safe_parameter_hint="limit",
            )
        if request.adjustment_basis not in {
            DailyMarketBarAdjustmentBasis.RAW,
            DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED,
        }:
            raise AlpacaProviderError(
                AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST,
                safe_parameter_hint="adjustment",
            )

    def _http_request(
        self,
        request: FetchCompletedDailyBarsRequest,
        page_token: str | None,
    ) -> HttpRequest:
        key_id = self._settings.api_key_id
        secret = self._settings.api_secret_key
        cutoff = request.completed_through_session_date
        if key_id is None or secret is None or cutoff is None:
            raise AlpacaProviderError(AlpacaErrorCategory.CONFIGURATION_MISSING)
        lookback = max(45, request.requested_session_count * 3)
        start = datetime.combine(cutoff.value - timedelta(days=lookback), datetime.min.time(), UTC)
        end = datetime.combine(cutoff.value + timedelta(days=1), datetime.min.time(), UTC)
        adjustment = (
            "split"
            if request.adjustment_basis is DailyMarketBarAdjustmentBasis.SPLIT_ADJUSTED
            else "raw"
        )
        limit = min(
            10_000,
            max(request.requested_session_count * 3, request.requested_session_count + 20),
        )
        query = [
            ("timeframe", "1Day"),
            ("feed", self._settings.feed),
            ("adjustment", adjustment),
            ("currency", "USD"),
            ("sort", "asc"),
            ("start", _rfc3339(start)),
            ("end", _rfc3339(end)),
            ("limit", str(limit)),
            ("asof", cutoff.serialize()),
        ]
        if page_token is not None:
            query.append(("page_token", page_token))
        return HttpRequest(
            method="GET",
            path=f"/v2/stocks/{request.symbol.value}/bars",
            query=tuple(query),
            headers=(
                ("APCA-API-KEY-ID", key_id.reveal()),
                ("APCA-API-SECRET-KEY", secret.reveal()),
            ),
        )

    def _send_with_retry(self, request: HttpRequest) -> HttpResponse:
        last_category = AlpacaErrorCategory.HTTP_TRANSIENT_FAILURE
        last_status: int | None = None
        last_code: int | None = None
        last_hint: str | None = None
        for attempt in range(1, self._settings.maximum_retry_attempts + 1):
            self._rate_limiter.acquire()
            try:
                response = self._transport.send(
                    self._settings.base_url,
                    request,
                    connect_timeout_seconds=self._settings.connect_timeout_seconds,
                    read_timeout_seconds=self._settings.read_timeout_seconds,
                )
            except TimeoutError:
                last_category = AlpacaErrorCategory.HTTP_TIMEOUT
                last_status = last_code = None
                last_hint = None
            except OSError:
                last_category = AlpacaErrorCategory.HTTP_TRANSIENT_FAILURE
                last_status = last_code = None
                last_hint = None
            else:
                if response.status_code < 400:
                    return response
                category = _http_category(response.status_code)
                code, hint = _provider_error_metadata(response)
                if response.status_code not in _TRANSIENT_STATUSES:
                    raise AlpacaProviderError(
                        category,
                        http_status=response.status_code,
                        provider_code=code,
                        safe_parameter_hint=hint,
                    )
                last_category = category
                last_status = response.status_code
                last_code = code
                last_hint = hint
            if attempt < self._settings.maximum_retry_attempts:
                self._sleeper(min(8.0, float(2 ** (attempt - 1))))
        raise AlpacaProviderError(
            last_category,
            http_status=last_status,
            provider_code=last_code,
            safe_parameter_hint=last_hint,
        )

    @staticmethod
    def _payload(response: HttpResponse) -> dict[str, Any]:
        try:
            payload = json.loads(
                response.body.decode("utf-8"),
                parse_float=Decimal,
                parse_int=int,
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID) from None
        if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
            raise AlpacaProviderError(AlpacaErrorCategory.RESPONSE_SCHEMA_INVALID)
        return payload


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_category(status: int) -> AlpacaErrorCategory:
    if status in {400, 422}:
        return AlpacaErrorCategory.PROVIDER_REJECTED_REQUEST
    if status == 401:
        return AlpacaErrorCategory.AUTHENTICATION_REJECTED
    if status == 403:
        return AlpacaErrorCategory.ACCESS_FORBIDDEN
    if status == 404:
        return AlpacaErrorCategory.INSTRUMENT_NOT_FOUND
    if status == 429:
        return AlpacaErrorCategory.RATE_LIMITED
    if status in {500, 502, 503, 504}:
        return AlpacaErrorCategory.HTTP_TRANSIENT_FAILURE
    return AlpacaErrorCategory.HTTP_PERMANENT_FAILURE


def _provider_error_metadata(response: HttpResponse) -> tuple[int | None, str | None]:
    try:
        payload = json.loads(response.body.decode("utf-8"), parse_int=int)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    code = payload.get("code")
    provider_code = code if isinstance(code, int) and not isinstance(code, bool) else None
    candidate = payload.get("parameter")
    if isinstance(candidate, str) and candidate.strip().lower() in _SAFE_PARAMETER_HINTS:
        return provider_code, candidate.strip().lower()
    message = payload.get("message")
    if isinstance(message, str):
        normalized = message.lower()
        hint = next((name for name in _SAFE_PARAMETER_HINTS if name in normalized), None)
        return provider_code, hint
    return provider_code, None
