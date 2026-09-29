"""Extract only documented CSN entity references, never arbitrary column refs."""
from typing import Any


def references(definition: dict[str, Any]) -> list[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()

    def source(value, path):
        if not isinstance(value, dict):
            return
        ref = value.get("ref")
        if isinstance(ref, list) and ref:
            first = ref[0]
            name = first.get("id") if isinstance(first, dict) else first
            if isinstance(name, str):
                found.add((name, "source", path + "/ref/0"))
        if "join" in value and isinstance(value.get("args"), list):
            for index, arg in enumerate(value["args"]):
                source(arg, f"{path}/args/{index}")

    def query(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("val", "ref") or key.startswith("@"):
                    continue
                if key == "from":
                    source(child, path + "/from")
                query(child, path + "/" + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                query(child, f"{path}/{index}")

    def elements(value, path):
        if not isinstance(value, dict):
            return
        for key, element in value.items():
            if not isinstance(element, dict):
                continue
            target = element.get("target")
            if element.get("type") in ("cds.Association", "cds.Composition") and isinstance(target, str):
                found.add((target, "association", f"{path}/{key}/target"))
            elements(element.get("elements"), f"{path}/{key}/elements")

    for key in ("query", "projection"):
        query(definition.get(key), "/" + key)
    elements(definition.get("elements"), "/elements")
    return sorted(found)
