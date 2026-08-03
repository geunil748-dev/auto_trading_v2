"""Secret-safe injectable HTTP boundary using only the standard library."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class HttpRequest:
    method: str
    path: str
    query: tuple[tuple[str, str], ...]
    headers: tuple[tuple[str, str], ...] = ()

    def __repr__(self) -> str:
        names = tuple(name for name, _value in self.query)
        return f"HttpRequest(method={self.method!r}, path={self.path!r}, query_names={names!r})"


@dataclass(frozen=True, slots=True, repr=False)
class HttpResponse:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def __repr__(self) -> str:
        return f"HttpResponse(status_code={self.status_code!r}, body_length={len(self.body)!r})"


class HttpTransport(Protocol):
    def send(
        self,
        base_url: str,
        request: HttpRequest,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse: ...


class UrllibHttpTransport:
    """Perform one TLS-verified request without changing global opener state."""

    def send(
        self,
        base_url: str,
        request: HttpRequest,
        *,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        query = urlencode(request.query)
        target = f"{base_url}{request.path}?{query}" if query else f"{base_url}{request.path}"
        urllib_request = Request(
            target,
            method=request.method,
            headers=dict(request.headers),
        )
        timeout = max(connect_timeout_seconds, read_timeout_seconds)
        try:
            with urlopen(urllib_request, timeout=timeout) as response:  # noqa: S310
                return _response(response.status, response.headers.items(), response.read)
        except HTTPError as exc:
            return _response(exc.code, exc.headers.items(), exc.read)
        except TimeoutError:
            raise TimeoutError("market-data HTTP timeout") from None
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError("market-data HTTP timeout") from None
            raise OSError("market-data HTTP connection failure") from None


def _response(
    status_code: int,
    headers: Iterable[tuple[str, str]],
    reader: Callable[[int], bytes],
) -> HttpResponse:
    body = reader(_MAX_RESPONSE_BYTES + 1)
    if len(body) > _MAX_RESPONSE_BYTES:
        body = body[:_MAX_RESPONSE_BYTES]
    return HttpResponse(
        status_code=int(status_code),
        headers=tuple((str(name).lower(), str(value)) for name, value in headers),
        body=bytes(body),
    )
