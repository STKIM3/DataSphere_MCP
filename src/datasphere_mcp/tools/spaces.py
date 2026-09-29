from ..models.common import Environment, Offset, Page, PageSize, Result
from ..models.objects import SpacePage
from .common import READ_METADATA, invoke


def register(mcp, runtime):
    @mcp.tool(**READ_METADATA)
    async def list_spaces(environment: Environment, limit: PageSize = 100,
                          offset: Offset = 0) -> Result[SpacePage]:
        """List accessible spaces. Explicit environment; bounded pagination."""
        return await invoke(runtime, "list_spaces", {"environment": environment}, lambda:
            runtime.services(environment).spaces.list_spaces(environment, Page(limit=limit, offset=offset)), Result[SpacePage])
