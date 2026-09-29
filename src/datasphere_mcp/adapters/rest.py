import asyncio
import json
from typing import Any

import httpx

from ..auth.oauth import OAuthProvider
from ..config import TenantConfig
from ..exceptions import (
    APIError, AuthenticationError, AuthorizationError, ObjectNotFoundError,
    OperationTimeout, ResponseFormatError, ResponseTooLarge,
)


class DatasphereRESTAdapter:
    """Bounded internal GET transport for explicitly supported SAP API paths."""

    def __init__(self, tenant: TenantConfig, auth: OAuthProvider,
                 client: httpx.AsyncClient, max_bytes: int):
        self.tenant, self.auth, self.client, self.max_bytes = tenant, auth, client, max_bytes

    async def _get_json(self, path: str, params: dict[str, int]) -> Any:
        # Not exposed as an MCP tool. Only the documented catalog route is enabled.
        if path != "/api/v1/datasphere/consumption/catalog/spaces":
            raise APIError()
        try:
            async with asyncio.timeout(60):
                for attempt in range(3):
                    token = await self.auth.get_token()
                    async with self.client.stream(
                        "GET", self.tenant.base_url + path, params=params,
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                        timeout=httpx.Timeout(30, connect=10), follow_redirects=False,
                    ) as response:
                        status = response.status_code
                        if status == 401:
                            self.auth.invalidate()
                            if attempt == 0:
                                continue
                            raise AuthenticationError()
                        if status == 403:
                            raise AuthorizationError()
                        if status == 404:
                            raise ObjectNotFoundError()
                        if status in (429, 502, 503, 504) and attempt < 2:
                            retry_after = response.headers.get("Retry-After", "")
                            delay = min(float(retry_after), 5) if retry_after.isdigit() else 0.25 * 2 ** attempt
                        else:
                            if status != 200:
                                raise APIError()
                            body = bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body) > self.max_bytes:
                                    raise ResponseTooLarge()
                            try:
                                return json.loads(body)
                            except ValueError:
                                raise ResponseFormatError() from None
                    await asyncio.sleep(delay)
        except TimeoutError:
            raise OperationTimeout() from None
        except httpx.HTTPError:
            raise APIError() from None
        raise APIError()
