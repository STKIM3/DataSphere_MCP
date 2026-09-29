from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .common import Identifier, Page, SpaceRequest


class DatasphereObjectType(StrEnum):
    LOCAL_TABLE = "local-tables"
    REMOTE_TABLE = "remote-tables"
    VIEW = "views"
    DATA_FLOW = "data-flows"
    REPLICATION_FLOW = "replication-flows"
    TRANSFORMATION_FLOW = "transformation-flows"
    TASK_CHAIN = "task-chains"
    ANALYTIC_MODEL = "analytic-models"
    BUSINESS_ENTITY = "business-entities"
    FACT_MODEL = "fact-models"
    CONSUMPTION_MODEL = "consumption-models"
    DATA_ACCESS_CONTROL = "data-access-controls"
    PACKAGE = "packages"


class ObjectListRequest(SpaceRequest, Page):
    object_type: DatasphereObjectType


class ObjectRequest(SpaceRequest):
    object_type: DatasphereObjectType
    technical_name: Identifier


class ObjectSummary(BaseModel):
    technical_name: str
    object_type: DatasphereObjectType
    business_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObjectPage(BaseModel):
    items: list[ObjectSummary]
    next_offset: int | None = None


class DatasphereObject(BaseModel):
    technical_name: str
    object_type: DatasphereObjectType
    definition: dict[str, Any]


class Space(BaseModel):
    space: str
    business_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpacePage(BaseModel):
    items: list[Space]
    next_offset: int | None = None
    source: str
