from ..models.common import Environment, Identifier, Result
from ..models.dependencies import DependencyGraph, DependencyRequest, Depth, Direction
from ..models.objects import DatasphereObjectType
from .common import READ_METADATA, invoke


def register(mcp, runtime):
    @mcp.tool(**READ_METADATA)
    async def get_dependencies(environment: Environment, space: Identifier, object_type: DatasphereObjectType,
                               technical_name: Identifier, direction: Direction = Direction.UPSTREAM,
                               max_depth: Depth = 3) -> Result[DependencyGraph]:
        """Infer bounded upstream CSN dependencies with evidence. DOWNSTREAM/BOTH are unsupported.

        complete=false means this is partial metadata extraction, not authoritative tenant lineage.
        """
        return await invoke(runtime, "get_dependencies", {
            "environment": environment, "space": space, "object_type": object_type,
            "technical_name": technical_name,
        }, lambda: runtime.services(environment).dependencies.get_dependencies(DependencyRequest(
            environment=environment, space=space, object_type=object_type, technical_name=technical_name,
            direction=direction, max_depth=max_depth,
        )), Result[DependencyGraph])
