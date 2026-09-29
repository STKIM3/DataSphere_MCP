import time
from dataclasses import dataclass

from pydantic import SecretStr


@dataclass(repr=False)
class TokenCache:
    token: SecretStr | None = None
    expires_at: float = 0

    def get(self) -> str | None:
        if self.token and time.monotonic() < self.expires_at:
            return self.token.get_secret_value()
        return None

    def put(self, token: str, expires_in: float) -> None:
        self.token = SecretStr(token)
        self.expires_at = time.monotonic() + max(0, expires_in - min(30, expires_in / 10))

    def clear(self) -> None:
        self.token = None
        self.expires_at = 0
