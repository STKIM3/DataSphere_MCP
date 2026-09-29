import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ..auth.oauth import OAuthProvider
from ..config import Settings, TenantConfig
from ..exceptions import (
    AuthenticationError, AuthorizationError, CLIExecutionError, ConfigurationError,
    ObjectNotFoundError, OperationTimeout, ResponseFormatError, ResponseTooLarge,
)
from ..models.objects import ObjectListRequest, ObjectRequest


class DatasphereCLIAdapter:
    """Only fixed read commands. Node entrypoint avoids Windows .cmd shell execution."""

    def __init__(self, settings: Settings, tenant: TenantConfig, auth: OAuthProvider):
        self.settings = settings
        self.tenant = tenant
        self.auth = auth
        self._lock = asyncio.Lock()

    async def list_spaces(self) -> Any:
        return await self._execute(["spaces", "list"])

    async def list_objects(self, request: ObjectListRequest) -> Any:
        request = ObjectListRequest.model_validate(request.model_dump())
        return await self._execute([
            "objects", request.object_type.value, "list", "--space", request.space,
            "--top", str(request.limit), "--skip", str(request.offset),
        ])

    async def read_object(self, request: ObjectRequest) -> dict[str, Any]:
        request = ObjectRequest.model_validate(request.model_dump())
        result = await self._execute([
            "objects", request.object_type.value, "read", "--space", request.space,
            "--technical-name", request.technical_name,
        ])
        if not isinstance(result, dict) or not result:
            raise ResponseFormatError()
        return result

    async def _read_bounded(self, stream: asyncio.StreamReader) -> bytes:
        data = bytearray()
        while chunk := await stream.read(65536):
            data.extend(chunk)
            if len(data) > self.settings.max_response_bytes:
                raise ResponseTooLarge()
        return bytes(data)

    async def _execute(self, args: list[str]) -> Any:
        async with self._lock:
            entry = self.settings.cli_entry.resolve()
            node = shutil.which(self.settings.node_executable)
            if not entry.is_file() or entry.suffix != ".js" or not node:
                raise ConfigurationError()
            token = await self.auth.get_token()
            # Do not inherit CLI options, other tenants' credentials, NODE_OPTIONS,
            # TLS bypass switches, or the user's shared SAP login/cache.
            child_env = {key: value for key, value in os.environ.items() if key.upper() in {
                "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT",
                "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "NODE_EXTRA_CA_CERTS",
            }}
            child_env.update({
                "ACCESS_TOKEN": token, "HOST": self.tenant.base_url,
                "LOG_LEVEL": "2", "NO_COLOR": "1",
            })
            with TemporaryDirectory(prefix="datasphere-read-") as directory:
                # SAP CLI prioritizes its cached token over ACCESS_TOKEN. Give each
                # invocation a fresh profile so refreshed tokens cannot be shadowed.
                child_env.update({"HOME": directory, "USERPROFILE": directory})
                output = Path(directory) / "result.json"
                try:
                    async with asyncio.timeout(self.settings.cli_timeout):
                        # Commands are tenant-discovered. A fresh profile must be
                        # initialized through the official CLI before spaces/objects
                        # commands exist. This only writes the temporary local cache.
                        await self._run_process(node, entry,
                            ["config", "cache", "init", "--host", self.tenant.base_url],
                            directory, child_env)
                        await self._run_process(node, entry,
                            [*args, "--host", self.tenant.base_url, "--output", str(output), "--no-pretty"],
                            directory, child_env)
                    if not output.is_file():
                        raise ResponseFormatError()
                    if output.stat().st_size > self.settings.max_response_bytes:
                        raise ResponseTooLarge()
                    try:
                        return json.loads(output.read_text(encoding="utf-8-sig"))
                    except (ValueError, UnicodeError):
                        raise ResponseFormatError() from None
                except TimeoutError:
                    raise OperationTimeout() from None
                except OSError:
                    raise CLIExecutionError() from None

    async def _run_process(self, node: str, entry: Path, args: list[str],
                           directory: str, child_env: dict[str, str]) -> None:
        process = None
        readers = []
        try:
            process = await asyncio.create_subprocess_exec(
                node, str(entry), *args, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=directory, env=child_env,
            )
            readers = [asyncio.create_task(self._read_bounded(process.stdout)),
                       asyncio.create_task(self._read_bounded(process.stderr))]
            stdout, stderr = await asyncio.gather(*readers)
            await process.wait()
            if process.returncode:
                # Error-level diagnostics are captured solely for classification.
                # Never return or log upstream text, which can contain credentials.
                diagnostic = (stderr + stdout).decode("utf-8", errors="replace")
                if re.search(r"\b401\b", diagnostic):
                    self.auth.invalidate()
                    raise AuthenticationError()
                if re.search(r"\b403\b", diagnostic):
                    raise AuthorizationError()
                if re.search(r"\b404\b", diagnostic):
                    raise ObjectNotFoundError()
                raise CLIExecutionError()
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            if readers:
                await asyncio.gather(*readers, return_exceptions=True)

    def close(self):
        """Per-invocation temporary profiles are already cleaned up."""
