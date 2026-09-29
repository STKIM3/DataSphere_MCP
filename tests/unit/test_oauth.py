import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from datasphere_mcp.auth.oauth import OAuthProvider
from datasphere_mcp.auth.token_cache import TokenCache
from datasphere_mcp.config import TenantConfig
from datasphere_mcp.exceptions import AuthenticationError, ConfigurationError
from datasphere_mcp.security import SecretRedactor


def config():
    return TenantConfig(base_url="https://dev.example", token_url="https://auth.example/token",
                        client_id=SecretStr("client-test"), client_secret=SecretStr("secret-test"),
                        refresh_token=SecretStr("refresh-one"))


async def test_cache_single_flight_and_refresh_rotation():
    bodies = []
    def handler(request):
        bodies.append(request.content.decode())
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, json={"access_token": "access-test", "expires_in": 3600,
                                         "refresh_token": "refresh-two"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        auth = OAuthProvider(config(), client, SecretRedactor())
        assert await asyncio.gather(*(auth.get_token() for _ in range(6))) == ["access-test"] * 6
        assert len(bodies) == 1
        assert "refresh-one" in bodies[0]
        auth.invalidate()
        await auth.get_token()
        assert "refresh-two" in bodies[1]
        assert "access-test" not in repr(auth.cache)


@pytest.mark.parametrize("status,body", [(400, {"error": "secret-test"}), (302, {}),
    (200, {"access_token": "x", "expires_in": -1}), (200, {"access_token": "x", "expires_in": "nan"})])
async def test_oauth_errors_are_safe(status, body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))) as client:
        with pytest.raises(AuthenticationError) as error:
            await OAuthProvider(config(), client, SecretRedactor()).get_token()
        assert "secret-test" not in str(error.value)


async def test_secrets_file(tmp_path):
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"client_id": "id", "client_secret": "secret", "refresh_token": "refresh",
                               "token_url": "https://auth.example/token", "host": "https://dev.example"}))
    cfg = TenantConfig(base_url="https://dev.example", secrets_file=str(path))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, json={"access_token": "test", "expires_in": 3600}))) as client:
        assert await OAuthProvider(cfg, client, SecretRedactor()).get_token() == "test"
        cfg.base_url = "https://other.example"
        with pytest.raises(ConfigurationError):
            await OAuthProvider(cfg, client, SecretRedactor()).get_token()


async def test_client_credentials():
    cfg = config()
    cfg.auth_mode = "client_credentials"
    def handler(request):
        assert b"grant_type=client_credentials" in request.content
        assert b"refresh_token" not in request.content
        assert request.headers["x-sap-sac-custom-auth"] == "false"
        return httpx.Response(200, json={"access_token": "test", "expires_in": 60})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await OAuthProvider(cfg, client, SecretRedactor()).get_token()


def test_expired_token():
    cache = TokenCache()
    cache.put("test", 0)
    assert cache.get() is None


async def test_cli_session_array_selects_exact_tenant(tmp_path):
    path = tmp_path / "sessions.json"
    rows = [{"tenantUrl": "https://other.example", "client_id": "wrong", "client_secret": "wrong",
             "token_url": "https://wrong.example/token", "refresh_token": "wrong"},
            {"tenantUrl": "https://dev.example", "client_id": "sb-dev", "client_secret": "secret",
             "token_url": "https://auth.example/token", "refresh_token": "right"}]
    path.write_text(json.dumps(rows))
    cfg = TenantConfig(base_url="https://dev.example", secrets_file=str(path))
    def handler(request):
        assert request.url.host == "auth.example"
        assert b"refresh_token=right" in request.content
        assert b"client_id=" not in request.content
        assert request.headers["x-sap-sac-custom-auth"] == "true"
        return httpx.Response(200, json={"access_token": "ok", "expires_in": 3600})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await OAuthProvider(cfg, client, SecretRedactor()).get_token()
        path.write_text(json.dumps(rows + [rows[1]]))
        with pytest.raises(ConfigurationError):
            await OAuthProvider(cfg, client, SecretRedactor()).get_token()
