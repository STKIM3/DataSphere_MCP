from collections import deque

from pydantic import ValidationError

from ..config import Settings
from ..exceptions import DatasphereError, UnsupportedCapability
from ..models.common import Result
from ..models.dependencies import DependencyEdge, DependencyGraph, DependencyNode, DependencyRequest, Direction
from ..models.objects import DatasphereObjectType, ObjectListRequest, ObjectRequest
from ..security import authorize
from .csn import references
from .object_service import ObjectService


class DependencyService:
    def __init__(self, objects: ObjectService, settings: Settings):
        self.objects, self.settings = objects, settings

    async def get_dependencies(self, request: DependencyRequest) -> Result[DependencyGraph]:
        request = DependencyRequest.model_validate(request.model_dump())
        authorize(request.environment)
        if request.direction != Direction.UPSTREAM:
            raise UnsupportedCapability()
        root_request = ObjectRequest(**request.model_dump(exclude={"direction", "max_depth"}))
        root = f"{request.space}:{request.technical_name}"
        root_object = await self.objects.get_object(root_request)
        definitions = root_object.data.definition.get("definitions", {})
        if not isinstance(definitions, dict) or not isinstance(definitions.get(request.technical_name), dict):
            raise UnsupportedCapability()
        root_definition = definitions[request.technical_name]
        if root_definition.get("kind") != "entity" and not any(
            key in root_definition for key in ("query", "projection", "elements")
        ):
            raise UnsupportedCapability()
        nodes = {request.technical_name: DependencyNode(
            id=root, space=request.space, technical_name=request.technical_name,
            object_type=request.object_type, resolved=True,
        )}
        edges = []
        warnings = [
            "Derived from CSN query/projection sources and association targets; not authoritative SAP lineage. "
            "SQL text, custom model formats, DAC annotations and cross-space resolution are not covered."
        ]
        queue = deque([(request.technical_name, definitions[request.technical_name], 0)])
        visited = set()
        inventory: dict[str, set[DatasphereObjectType]] | None = None
        truncated = False
        while queue:
            name, definition, depth = queue.popleft()
            if name in visited:
                continue
            visited.add(name)
            refs = references(definition)
            if depth >= request.max_depth:
                if refs:
                    truncated = True
                continue
            if refs and inventory is None:
                inventory, inventory_warnings, inventory_truncated = await self._inventory(request)
                warnings.extend(inventory_warnings)
                truncated |= inventory_truncated
            for target, kind, evidence in refs:
                if target not in nodes:
                    if len(nodes) >= self.settings.max_dependency_nodes:
                        truncated = True
                        continue
                    candidates = (inventory or {}).get(target, set())
                    target_type = next(iter(candidates)) if len(candidates) == 1 else None
                    node = DependencyNode(id=f"{request.space}:{target}", space=request.space,
                                          technical_name=target, object_type=target_type)
                    nodes[target] = node
                    if target_type is not None:
                        try:
                            child_request = ObjectRequest(environment=request.environment, space=request.space,
                                                          object_type=target_type, technical_name=target)
                            child = await self.objects.get_object(child_request)
                            child_defs = child.data.definition.get("definitions", {})
                            child_def = child_defs.get(target) if isinstance(child_defs, dict) else None
                            if isinstance(child_def, dict):
                                node.resolved = True
                                queue.append((target, child_def, depth + 1))
                            else:
                                warnings.append("A referenced object uses an unsupported metadata format.")
                        except (DatasphereError, ValidationError):
                            warnings.append("A referenced object could not be resolved with the current identity.")
                    else:
                        warnings.append("A reference has no unambiguous object type in the bounded space inventory.")
                edges.append(DependencyEdge(source=nodes[name].id, target=nodes[target].id,
                                            kind=kind, evidence=f"definitions/{name}{evidence}"))
        if truncated:
            warnings.append("Depth, inventory or node limit reached; the graph is truncated.")
        graph = DependencyGraph(root=root, direction=request.direction, nodes=list(nodes.values()),
                                edges=edges, truncated=truncated, complete=False)
        return Result[DependencyGraph](environment=request.environment, space=request.space, data=graph,
                      warnings=list(dict.fromkeys(warnings)))

    async def _inventory(self, request):
        inventory: dict[str, set[DatasphereObjectType]] = {}
        warnings = []
        remaining = self.settings.max_inventory_objects
        # These types can be sources in the documented CSN representation.
        for kind in (DatasphereObjectType.LOCAL_TABLE, DatasphereObjectType.REMOTE_TABLE,
                     DatasphereObjectType.VIEW, DatasphereObjectType.ANALYTIC_MODEL):
            offset = 0
            previous_pages = set()
            while remaining > 0:
                try:
                    result = await self.objects.list_objects(ObjectListRequest(
                        environment=request.environment, space=request.space, object_type=kind,
                        limit=min(200, remaining), offset=offset,
                    ))
                except DatasphereError:
                    warnings.append("One inventory object type was unavailable; dependency resolution is partial.")
                    break
                names = tuple(item.technical_name for item in result.data.items)
                if names and names in previous_pages:
                    warnings.append("SAP returned a repeated inventory page; pagination was stopped.")
                    return inventory, warnings, True
                previous_pages.add(names)
                for item in result.data.items:
                    inventory.setdefault(item.technical_name, set()).add(kind)
                    remaining -= 1
                if result.data.next_offset is None:
                    break
                offset = result.data.next_offset
            if remaining == 0:
                return inventory, warnings, True
        return inventory, warnings, False
