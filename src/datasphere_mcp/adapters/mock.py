from copy import deepcopy

from ..exceptions import ObjectNotFoundError
from ..models.objects import ObjectListRequest, ObjectRequest


def fixtures():
    return {
        ("local-tables", "T_TEST"): {"definitions": {"T_TEST": {
            "kind": "entity", "@EndUserText.label": "Test table",
            "elements": {"ID": {"type": "cds.Integer", "key": True}},
        }}},
        ("views", "V_TEST"): {"definitions": {"V_TEST": {
            "kind": "entity", "query": {"SELECT": {"from": {"ref": ["T_TEST"]}}},
        }}},
        # Synthetic CSN fixture, not a captured SAP Analytic Model payload.
        ("analytic-models", "AM_TEST"): {"definitions": {"AM_TEST": {
            "kind": "entity", "query": {"SELECT": {"from": {"ref": ["V_TEST"]}}},
        }}},
    }


class MockAdapter:
    def __init__(self):
        self.objects = fixtures()

    async def list_spaces(self):
        return [{"spaceId": "BSG_BI", "businessName": "Mock BI"}]

    async def list_objects(self, request: ObjectListRequest):
        if request.space != "BSG_BI":
            raise ObjectNotFoundError()
        items = [{"technicalName": name} for kind, name in self.objects if kind == request.object_type]
        return deepcopy(items[request.offset:request.offset + request.limit])

    async def read_object(self, request: ObjectRequest):
        if request.space != "BSG_BI":
            raise ObjectNotFoundError()
        try:
            return deepcopy(self.objects[(request.object_type, request.technical_name)])
        except KeyError:
            raise ObjectNotFoundError() from None
