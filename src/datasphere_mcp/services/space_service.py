from ..adapters.base import ReadAdapter
from ..adapters.odata import DatasphereODataAdapter
from ..exceptions import ResponseFormatError
from ..models.common import Environment, Page, Result
from ..models.objects import Space, SpacePage
from ..security import authorize
from .parsing import name_from, rows


class SpaceService:
    def __init__(self, adapter: ReadAdapter, catalog: DatasphereODataAdapter | None = None):
        self.adapter, self.catalog = adapter, catalog

    async def list_spaces(self, environment: Environment, page: Page) -> Result[SpacePage]:
        authorize(environment)
        page = Page.model_validate(page.model_dump())
        if self.catalog:
            payload = await self.catalog.list_spaces(page)
            records = rows(payload, "spaces")
            more = bool(payload.get("@odata.nextLink")) or len(records) == page.limit
            if len(records) > page.limit or (more and not records):
                raise ResponseFormatError()
            source = "consumption_catalog"
            warnings = ["Consumption catalog scope only; this is not the full modeling-space inventory."]
        else:
            records = rows(await self.adapter.list_spaces(), "spaces")
            more = len(records) > page.offset + page.limit
            records = records[page.offset:page.offset + page.limit]
            source, warnings = "cli", []
        items = []
        for record in records:
            if isinstance(record, str):
                record = {"spaceId": record}
            if not isinstance(record, dict):
                raise ResponseFormatError()
            items.append(Space(space=name_from(record, "spaceId", "name", "id"),
                               business_name=record.get("businessName"), metadata=record))
        return Result[SpacePage](environment=environment, data=SpacePage(
            items=items, next_offset=page.offset + len(items) if more else None, source=source,
        ), warnings=warnings)
