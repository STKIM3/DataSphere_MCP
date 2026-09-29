from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .objects import DatasphereObjectType, ObjectRequest


class Direction(StrEnum):
    UPSTREAM = "UPSTREAM"
    DOWNSTREAM = "DOWNSTREAM"
    BOTH = "BOTH"


Depth = Annotated[int, Field(ge=1, le=10, strict=True)]


class DependencyRequest(ObjectRequest):
    direction: Direction = Direction.UPSTREAM
    max_depth: Depth = 3


class DependencyNode(BaseModel):
    id: str
    space: str
    technical_name: str
    object_type: DatasphereObjectType | None = None
    resolved: bool = False


class DependencyEdge(BaseModel):
    source: str
    target: str
    kind: Literal["source", "association"]
    evidence: str


class DependencyGraph(BaseModel):
    root: str
    direction: Direction
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    source: Literal["csn"] = "csn"
    complete: bool = False
    truncated: bool = False
