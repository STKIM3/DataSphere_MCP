from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from datasphere_mcp.adapters.odata import DatasphereODataAdapter
from datasphere_mcp.adapters.rest import DatasphereRESTAdapter
from datasphere_mcp.config import TenantConfig
from datasphere_mcp.exceptions import APIError, AuthorizationError, ResponseFormatError, ResponseTooLarge
from datasphere_mcp.models.common import Page


async def run(handler, max_bytes=1024):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    auth = Mock(get_token=AsyncMock(return_value="secret-token"), invalidate=Mock())
    rest = DatasphereRESTAdapter(TenantConfig(base_url="https://dev.example"), auth, client, max_bytes)
    return client, rest, auth


async def test_catalog_bounded_no_nextlink_follow():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == "/api/v1/datasphere/consumption/catalog/spaces"
        assert request.url.params["$top"] == "2"
        assert request.url.params["$skip"] == "4"
        return httpx.Response(200, json={"value": [{"name": "BSG_BI"}], "@odata.nextLink": "https://evil.example"})
    client, rest, _ = await run(handler)
    async with client:
        await DatasphereODataAdapter(rest).list_spaces(Page(limit=2, offset=4))
    assert len(calls) == 1


async def test_retry_and_401_refresh():
    statuses = iter([401, 503, 200])
    client, rest, auth = await run(lambda r: httpx.Response(next(statuses), json={"value": []}))
    async with client:
        assert await DatasphereODataAdapter(rest).list_spaces(Page()) == {"value": []}
    auth.invalidate.assert_called_once()
    assert auth.get_token.await_count == 3


@pytest.mark.parametrize("status,body,error", [(403, {}, AuthorizationError), (302, {}, APIError),
    (200, {"error": "secret"}, ResponseFormatError), (200, {"value": ["x" * 3000]}, ResponseTooLarge)])
async def test_safe_http_errors(status, body, error):
    client, rest, _ = await run(lambda r: httpx.Response(status, json=body))
    async with client:
        with pytest.raises(error):
            await DatasphereODataAdapter(rest).list_spaces(Page())


async def test_transport_does_not_accept_arbitrary_urls():
    client, rest, _ = await run(lambda r: pytest.fail("Network must not be reached"))
    async with client:
        with pytest.raises(APIError):
            await rest._get_json("https://evil.example", {})
