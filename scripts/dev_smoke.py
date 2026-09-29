"""Read-only real DEV acceptance check through the actual MCP tool protocol."""
import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values
from fastmcp import Client

from datasphere_mcp.config import Settings
from datasphere_mcp.server import create_server


async def smoke(settings: Settings, space: str, object_type: str, technical_name: str) -> dict:
    if settings.mock_mode:
        return {"success": False, "error": "MOCK_MODE_NOT_ALLOWED"}
    report = {"environment": "DEV", "space": space, "object_type": object_type,
              "technical_name": technical_name, "timestamp": datetime.now(UTC).isoformat(),
              "mock_mode": False, "steps": [], "success": False}
    async with Client(create_server(settings)) as client:
        common = {"environment": "DEV", "space": space, "object_type": object_type}
        calls = [
            ("list_spaces", {"environment": "DEV"}),
            ("list_objects", common),
            ("get_object", {**common, "technical_name": technical_name}),
            ("get_dependencies", {**common, "technical_name": technical_name, "direction": "UPSTREAM"}),
        ]
        for name, args in calls:
            found = False
            for _ in range(100):
                response = await client.call_tool(name, args, raise_on_error=False)
                body = response.structured_content or {}
                if response.is_error or not body.get("success"):
                    report["steps"].append({"tool": name, "success": False,
                                            "error": body.get("error", {"code": "MCP_ERROR"})})
                    return report
                data = body["data"]
                if name == "list_spaces":
                    found |= any(row["space"] == space for row in data["items"])
                elif name == "list_objects":
                    found |= any(row["technical_name"] == technical_name for row in data["items"])
                else:
                    found = True
                if found or data.get("next_offset") is None:
                    break
                args = {**args, "offset": data["next_offset"]}
            step = {"tool": name, "success": found, "warnings": body.get("warnings", [])}
            if name == "get_dependencies":
                step.update({"node_count": len(data["nodes"]), "edge_count": len(data["edges"]),
                             "complete": data["complete"], "truncated": data["truncated"]})
            report["steps"].append(step)
            if not found:
                step["error"] = {"code": "TARGET_NOT_FOUND_IN_BOUNDED_LIST"}
                return report
    report["success"] = True
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--space", default="BSG_BI")
    parser.add_argument("--object-type", default="local-tables")
    parser.add_argument("--technical-name", default="T_TEST")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    env_file = os.getenv("DSP_ENV_FILE", ".env")
    enabled = os.getenv("DSP_RUN_DEV_INTEGRATION", dotenv_values(env_file).get("DSP_RUN_DEV_INTEGRATION", "false"))
    if str(enabled).lower() != "true":
        print("DEV smoke disabled. Set DSP_RUN_DEV_INTEGRATION=true after configuring DEV OAuth.")
        return 2
    try:
        report = asyncio.run(smoke(Settings(_env_file=env_file), args.space, args.object_type, args.technical_name))
    except Exception:
        report = {"success": False, "error": "Check DEV configuration locally; raw errors are suppressed."}
    text = json.dumps(report, ensure_ascii=True, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
