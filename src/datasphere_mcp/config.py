from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .exceptions import ConfigurationError
from .models.common import Environment


def https_url(value: str, *, origin_only: bool = False) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or (origin_only and parsed.path not in ("", "/"))):
        raise ConfigurationError()
    return value.rstrip("/")


class TenantConfig(BaseModel):
    base_url: str = ""
    token_url: str = ""
    client_id: SecretStr = SecretStr("")
    client_secret: SecretStr = SecretStr("")
    refresh_token: SecretStr = SecretStr("")
    auth_mode: Literal["refresh_token", "client_credentials"] = "refresh_token"
    secrets_file: str = ""
    spaces_backend: Literal["cli", "catalog"] = "cli"
    allow_execute: bool = False
    allow_write: bool = False
    allow_delete: bool = False

    @field_validator("base_url", "token_url")
    @classmethod
    def validate_url(cls, value: str, info):
        if value:
            return https_url(value, origin_only=info.field_name == "base_url")
        return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DSP_", env_file=".env", env_file_encoding="utf-8-sig",
        env_nested_delimiter="_", env_nested_max_split=1, extra="ignore",
        hide_input_in_errors=True,
    )
    mock_mode: bool = False
    dev: TenantConfig = Field(default_factory=TenantConfig)
    qas: TenantConfig = Field(default_factory=TenantConfig)
    prd: TenantConfig = Field(default_factory=TenantConfig)
    cli_entry: Path = Path(".tools/node_modules/@sap/datasphere-cli/terminal.js")
    node_executable: str = "node"
    operation_timeout: float = Field(default=120, gt=0, le=600)
    cli_timeout: float = Field(default=60, gt=0, le=300)
    max_response_bytes: int = Field(default=26214400, ge=1024, le=52428800)
    max_dependency_nodes: int = Field(default=100, ge=1, le=500)
    max_inventory_objects: int = Field(default=500, ge=1, le=2000)

    def tenant(self, environment: Environment) -> TenantConfig:
        tenant = getattr(self, Environment(environment).value.lower())
        if not tenant.base_url:
            raise ConfigurationError()
        return tenant
