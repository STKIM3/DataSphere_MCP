from ..adapters.base import ReadAdapter
from ..exceptions import ResponseFormatError
from ..models.common import Result
from ..models.objects import (
    DatasphereObject, ObjectListRequest, ObjectPage, ObjectRequest, ObjectSummary,
)
from ..security import authorize
from .parsing import name_from, rows


class ObjectService:
    def __init__(self, adapter: ReadAdapter):
        self.adapter = adapter

    async def list_objects(self, request: ObjectListRequest) -> Result[ObjectPage]:
        request = ObjectListRequest.model_validate(request.model_dump())
        authorize(request.environment)
        records = rows(await self.adapter.list_objects(request), "objects")
        if len(records) > request.limit:
            raise ResponseFormatError()
        items = []
        for record in records:
            if not isinstance(record, dict):
                raise ResponseFormatError()
            items.append(ObjectSummary(
                technical_name=name_from(record, "technicalName"),
                object_type=request.object_type, business_name=record.get("businessName"),
                metadata=record,
            ))
        return Result[ObjectPage](environment=request.environment, space=request.space, data=ObjectPage(
            items=items, next_offset=request.offset + request.limit if len(items) == request.limit else None,
        ))

    async def get_object(self, request: ObjectRequest) -> Result[DatasphereObject]:
        request = ObjectRequest.model_validate(request.model_dump())
        authorize(request.environment)
        definition = await self.adapter.read_object(request)
        if not isinstance(definition, dict) or not definition:
            raise ResponseFormatError()
        return Result[DatasphereObject](environment=request.environment, space=request.space, data=DatasphereObject(
            technical_name=request.technical_name, object_type=request.object_type,
            definition=definition,
        ))
