from ..models.common import Environment, Identifier, Offset, PageSize, Result
from ..models.objects import (
    DatasphereObject, DatasphereObjectType, ObjectListRequest, ObjectPage, ObjectRequest,
)
from .common import READ_METADATA, invoke


def register(mcp, runtime):
    @mcp.tool(**READ_METADATA)
    async def list_objects(environment: Environment, space: Identifier, object_type: DatasphereObjectType,
                           limit: PageSize = 100, offset: Offset = 0) -> Result[ObjectPage]:
        """List modeling objects of a verified CLI type; follow next_offset for additional pages."""
        return await invoke(runtime, "list_objects", {
            "environment": environment, "space": space, "object_type": object_type,
        }, lambda: runtime.services(environment).objects.list_objects(ObjectListRequest(
            environment=environment, space=space, object_type=object_type, limit=limit, offset=offset,
        )), Result[ObjectPage])

    @mcp.tool(**READ_METADATA)
    async def get_object(environment: Environment, space: Identifier, object_type: DatasphereObjectType,
                         technical_name: Identifier) -> Result[DatasphereObject]:
        """Read the original SAP CSN/JSON definition, preserving metadata except secret redaction."""
        return await invoke(runtime, "get_object", {
            "environment": environment, "space": space, "object_type": object_type,
            "technical_name": technical_name,
        }, lambda: runtime.services(environment).objects.get_object(ObjectRequest(
            environment=environment, space=space, object_type=object_type, technical_name=technical_name,
        )), Result[DatasphereObject])
