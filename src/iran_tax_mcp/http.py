"""Shared async HTTP client for the Iranian tax sites.

Every tool goes through `request`: one Chrome-impersonating client (it keeps cookies, which ASP.NET WebForms needs),
capped concurrency, a small result cache and HTTP failures turned into `ToolError` messages the model can act on.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from curl_cffi.const import CurlOpt
from httpx_curl_cffi import AsyncCurlTransport
from mcp.server.mcpserver.exceptions import ToolError

HEADERS = {
    # User-Agent, sec-ch-ua and TLS come from the impersonated Chrome profile (see _get_client).
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}

MAX_CONCURRENCY = 4
JITTER = (0.1, 0.4)  # seconds before each uncached call
MAX_RETRIES = 2
MAX_RETRY_WAIT = 10  # cap for Retry-After and backoff, seconds
RETRY_DELAY = 0.5  # seconds, doubled per retry
MAX_BODY = 30_000_000  # bytes; a broad goods-ID export zip can reach a few MB
CACHE_MAX = 64
HOSTS = {"tax.gov.ir", "stuffid.tax.gov.ir", "regulation.tax.gov.ir"}

_transport: httpx.AsyncBaseTransport | None = None
_client: httpx.AsyncClient | None = None
_limit: asyncio.Semaphore | None = None
_proxy_index = 0
_retired: set[asyncio.Task] = set()
_cache: dict[Any, tuple[float, Any]] = {}
_STATE = re.compile(r'id="(__VIEWSTATE|__VIEWSTATEGENERATOR|__EVENTVALIDATION)" value="([^"]*)"')


class ApiError(ToolError):
    """A failed upstream call. `status` is the HTTP status, or None for network errors."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Swap the transport (tests use httpx.MockTransport). Drops the current client and the cache."""
    global _transport, _client, _limit, _proxy_index
    _transport, _client, _limit, _proxy_index = transport, None, None, 0
    _cache.clear()


async def cached(key: Any, ttl: float, make: Callable[[], Awaitable[Any]]) -> Any:
    """Return a cached result for `key` if younger than `ttl` seconds, else await `make()` and store it."""
    if (hit := _cache.get(key)) and time.monotonic() - hit[0] < ttl:
        return hit[1]
    value = await make()
    if len(_cache) >= CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic(), value)
    return value


def _proxies() -> list[str]:
    """IRAN_TAX_MCP_PROXY: one proxy URL, or a comma-separated list used one at a time."""
    return [p.strip() for p in os.environ.get("IRAN_TAX_MCP_PROXY", "").split(",") if p.strip()]


def _next_proxy(client: httpx.AsyncClient) -> None:
    """Sticky pool: move to the next proxy after a block or connect error; the next call rebuilds the client.

    Only the client that failed may rotate. The old client is closed late because other requests may still use it.
    """
    global _client, _limit, _proxy_index
    if len(_proxies()) < 2 or client is not _client:
        return
    _client, _limit, _proxy_index = None, None, _proxy_index + 1
    t = asyncio.create_task(_close_later(client))
    _retired.add(t)
    t.add_done_callback(_retired.discard)


async def _close_later(client: httpx.AsyncClient) -> None:
    await asyncio.sleep(90)  # longer than the 60 s read timeout
    await client.aclose()


def _get_client() -> tuple[httpx.AsyncClient, asyncio.Semaphore]:
    global _client, _limit
    if _client is None:
        # System proxy settings are ignored unless the user opts in with IRAN_TAX_MCP_PROXY. curl_cffi presents
        # Chrome's TLS/HTTP2 fingerprint and default headers. The proxy goes to the transport.
        proxies = _proxies()
        _client = httpx.AsyncClient(
            transport=_transport
            or AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
                curl_options={
                    CurlOpt.NOPROXY: "*"
                },  # httpx-curl-cffi drops its own NOPROXY unless this dict is non-empty
                proxy=proxies[_proxy_index % len(proxies)] if proxies else None,
                max_connections=2 * MAX_CONCURRENCY,
            ),
            headers=HEADERS,
            timeout=httpx.Timeout(60, connect=10),  # a goods-ID export takes ~15 s to build
            limits=httpx.Limits(max_connections=2 * MAX_CONCURRENCY),
            follow_redirects=False,
            trust_env=False,
        )
        _limit = asyncio.Semaphore(MAX_CONCURRENCY)
    assert _limit is not None
    return _client, _limit


async def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    """Send a request with retries and return the 2xx/3xx response (body already read).

    Retried up to MAX_RETRIES times on timeout, network error, 5xx or 429, with jittered exponential backoff or
    after Retry-After when sent. 4xx is never retried. Every call here is a read, so POST searches retry too.
    """
    host = httpx.URL(url).host
    if host not in HOSTS:
        raise ApiError(f"Refusing to call unexpected host {host}.")
    for attempt in range(MAX_RETRIES + 1):
        last = attempt == MAX_RETRIES
        wait = RETRY_DELAY * 2**attempt * random.uniform(1, 1.5)
        try:
            r = await _send(method, url, host, **kwargs)
        except ApiError as e:
            if last or e.status is not None:
                raise
            await asyncio.sleep(min(wait, MAX_RETRY_WAIT))
            continue
        if (r.status_code == 429 or r.status_code >= 500) and not last:
            await asyncio.sleep(min(_retry_after(r) or wait, MAX_RETRY_WAIT))
            continue
        break
    if r.status_code >= 400:
        raise ApiError(_status_message(r, host), r.status_code)
    return r


async def get_form(url: str) -> tuple[str, dict[str, str]]:
    """GET an ASP.NET WebForms page; return its HTML and the hidden state fields a postback must send back."""
    html = (await request("GET", url, headers={"Accept": "text/html,*/*"})).text
    return html, form_state(html)


def form_state(html: str) -> dict[str, str]:
    """The __VIEWSTATE, __VIEWSTATEGENERATOR and __EVENTVALIDATION values of a WebForms page."""
    state = {k: v for k, v in _STATE.findall(html)}
    if "__VIEWSTATE" not in state:
        raise ApiError("tax.gov.ir returned a page without its form state; the page layout may have changed.")
    return state


async def _send(method: str, url: str, host: str, **kwargs: Any) -> httpx.Response:
    client, limit = _get_client()
    try:
        async with limit:
            await asyncio.sleep(random.uniform(*JITTER))
            async with client.stream(method, url, **kwargs) as r:
                await _read_capped(r, host)
    except httpx.TimeoutException as e:
        raise ApiError(f"{host} did not answer in time. Try again in a moment.") from e
    except httpx.RequestError as e:
        if isinstance(e, httpx.ConnectError | httpx.ProxyError):
            _next_proxy(client)
        raise ApiError(
            f"Could not reach {host} ({type(e).__name__}). Iranian government sites often refuse foreign IPs: "
            "use an Iranian connection, or set IRAN_TAX_MCP_PROXY to a proxy that exits in Iran."
        ) from e
    if r.status_code in (403, 429):
        _next_proxy(client)
    return r


async def _read_capped(r: httpx.Response, host: str) -> None:
    """Read the body into the response, refusing anything over MAX_BODY so one huge answer cannot flood memory."""
    buf = bytearray()
    async for chunk in r.aiter_bytes():
        buf += chunk
        if len(buf) > MAX_BODY:
            raise ApiError(f"{host} sent a response over {MAX_BODY // 1_000_000} MB; refused.", r.status_code)
    r._content = bytes(buf)  # shortcut: sets httpx's private body field so .text/.json() work after streaming


def _retry_after(r: httpx.Response) -> float | None:
    """Seconds from a numeric Retry-After on a 429/503, else None (HTTP-date form is ignored)."""
    v = r.headers.get("retry-after", "")
    return float(v) if r.status_code in (429, 503) and v.replace(".", "", 1).isdigit() else None


def _status_message(r: httpx.Response, host: str) -> str:
    code = r.status_code
    if code == 403:
        return f"{host} blocked the request (HTTP 403). Try again later, or set IRAN_TAX_MCP_PROXY to a proxy that exits in Iran."
    if code == 404:
        return f"Not found on {host} (HTTP 404)."
    if code == 429:
        return f"{host} is rate limiting requests (HTTP 429). Wait a minute before retrying."
    if code >= 500:
        return f"{host} had a server error (HTTP {code}). Try again later."
    return f"{host} rejected the request (HTTP {code})."
