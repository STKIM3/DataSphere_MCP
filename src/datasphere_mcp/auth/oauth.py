import asyncio
import json
import math
from pathlib import Path

import httpx
from pydantic import SecretStr

from ..config import TenantConfig, https_url
from ..exceptions import AuthenticationError, ConfigurationError
from ..security import SecretRedactor
from .token_cache import TokenCache


class OAuthProvider:
    def __init__(self, config: TenantConfig, client: httpx.AsyncClient, redactor: SecretRedactor):
        self.config = config.model_copy(deep=True)
        self.client = client
        self.redactor = redactor
        self.cache = TokenCache()
        self.lock = asyncio.Lock()
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        if self.config.secrets_file:
            try:
                path = Path(self.config.secrets_file)
                if path.stat().st_size > 131072:
                    raise ConfigurationError()
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                # CLI 2026.19.0 exports an array, including other tenant sessions.
                # Select exactly one matching origin, never the first entry.
                if isinstance(data, list):
                    matches = [item for item in data if isinstance(item, dict)
                               and item.get("tenantUrl", "").rstrip("/") == self.config.base_url]
                    if len(matches) != 1:
                        raise ConfigurationError()
                    data = matches[0]
                if not isinstance(data, dict):
                    raise ConfigurationError()
                for key in ("client_id", "client_secret", "refresh_token"):
                    if not getattr(self.config, key).get_secret_value():
                        setattr(self.config, key, SecretStr(data.get(key, "")))
                if not self.config.token_url:
                    self.config.token_url = https_url(data.get("token_url", ""))
                stored_host = data.get("tenantUrl") or data.get("host")
                if stored_host and https_url(stored_host, origin_only=True) != self.config.base_url:
                    raise ConfigurationError()
            except (OSError, ValueError, TypeError, AttributeError):
                raise ConfigurationError() from None
        for key in ("client_id", "client_secret", "refresh_token"):
            self.redactor.add(getattr(self.config, key).get_secret_value())
        self._loaded = True

    async def get_token(self) -> str:
        async with self.lock:
            self._load()
            if cached := self.cache.get():
                return cached
            cfg = self.config
            if not (cfg.token_url and cfg.client_id.get_secret_value() and cfg.client_secret.get_secret_value()):
                raise ConfigurationError()
            custom_client = cfg.client_id.get_secret_value().startswith("sb-")
            body = {"grant_type": cfg.auth_mode, "response_type": "token"}
            if not custom_client:
                body["client_id"] = cfg.client_id.get_secret_value()
            if cfg.auth_mode == "refresh_token":
                if not cfg.refresh_token.get_secret_value():
                    raise ConfigurationError()
                body["refresh_token"] = cfg.refresh_token.get_secret_value()
            try:
                async with asyncio.timeout(30):
                    async with self.client.stream(
                        "POST", https_url(cfg.token_url), data=body,
                        auth=httpx.BasicAuth(cfg.client_id.get_secret_value(), cfg.client_secret.get_secret_value()),
                        headers={"Accept": "application/json",
                                 "x-sap-sac-custom-auth": str(custom_client).lower()}, follow_redirects=False,
                        timeout=httpx.Timeout(20, connect=10),
                    ) as response:
                        if response.status_code != 200:
                            raise AuthenticationError()
                        raw = bytearray()
                        async for part in response.aiter_bytes():
                            raw.extend(part)
                            if len(raw) > 131072:
                                raise AuthenticationError()
                data = json.loads(raw)
                token = data["access_token"]
                expires = float(data["expires_in"])
                if (not isinstance(token, str) or not token or not math.isfinite(expires)
                        or expires <= 0 or data.get("token_type", "Bearer").lower() != "bearer"):
                    raise AuthenticationError()
                self.redactor.add(token)
                if refreshed := data.get("refresh_token"):
                    if not isinstance(refreshed, str):
                        raise AuthenticationError()
                    cfg.refresh_token = SecretStr(refreshed)
                    self.redactor.add(refreshed)
                self.cache.put(token, expires)
                return token
            except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
                raise AuthenticationError() from None

    def invalidate(self) -> None:
        self.cache.clear()
