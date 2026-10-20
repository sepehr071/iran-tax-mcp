import json
from pathlib import Path

import httpx
import pytest
from mcp import Client

from iran_tax_mcp import http
from iran_tax_mcp.server import mcp

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fresh_http_client(monkeypatch):
    """The shared httpx client is bound to one event loop; each test gets a new loop."""
    monkeypatch.setattr(http, "RETRY_DELAY", 0)
    monkeypatch.setattr(http, "JITTER", (0, 0))
    http.set_transport(None)
    yield
    http.set_transport(None)


@pytest.fixture
def routes():
    """Fake upstream: routes["METHOD host/path"] or routes["host/path"] (any method) = bytes, or a
    callable(request) -> httpx.Response. Unknown routes return 404. Every request is appended to routes.calls.
    """

    class Routes(dict):
        calls: list[httpx.Request]

    table = Routes()
    table.calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        table.calls.append(request)
        key = request.url.host + request.url.path
        target = table.get(f"{request.method} {key}", table.get(key))
        if target is None:
            return httpx.Response(404, text="no fake route")
        if callable(target):
            return target(request)
        return httpx.Response(200, content=target)

    http.set_transport(httpx.MockTransport(handler))
    return table


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        call_tool = c.call_tool

        async def parsed(*args, **kwargs):
            result = await call_tool(*args, **kwargs)
            if not result.is_error:
                result.structured_content = json.loads(result.content[0].text)
            return result

        c.call_tool = parsed
        yield c
