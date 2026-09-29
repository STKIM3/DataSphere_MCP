from typing import Any

from ..exceptions import ResponseFormatError


def rows(payload: Any, collection: str) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("value", collection):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ResponseFormatError()


def name_from(row: dict, *keys: str) -> str:
    for key in keys:
        if isinstance(row.get(key), str) and row[key]:
            return row[key]
    raise ResponseFormatError()
