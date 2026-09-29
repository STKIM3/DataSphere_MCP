from ..exceptions import ResponseFormatError
from ..models.common import Page
from .rest import DatasphereRESTAdapter


class DatasphereODataAdapter:
    def __init__(self, rest: DatasphereRESTAdapter):
        self.rest = rest

    async def list_spaces(self, page: Page) -> dict:
        page = Page.model_validate(page.model_dump())
        result = await self.rest._get_json(
            "/api/v1/datasphere/consumption/catalog/spaces",
            {"$top": page.limit, "$skip": page.offset},
        )
        if not isinstance(result, dict) or not isinstance(result.get("value"), list):
            raise ResponseFormatError()
        # Never follow upstream nextLink URLs (which could point to another host).
        return result
