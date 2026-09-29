import importlib.util
import os
from pathlib import Path

from dotenv import dotenv_values
import pytest

from datasphere_mcp.config import Settings


pytestmark = pytest.mark.integration


async def test_real_dev_four_tools():
    env_file = os.getenv("DSP_ENV_FILE", ".env")
    values = {**dotenv_values(env_file), **os.environ}
    if values.get("DSP_RUN_DEV_INTEGRATION", "false").lower() != "true":
        pytest.skip("Real DEV OAuth not opted in; no tenant calls made")
    path = Path(__file__).parents[2] / "scripts" / "dev_smoke.py"
    spec = importlib.util.spec_from_file_location("dev_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = await module.smoke(Settings(_env_file=env_file),
        values.get("DSP_TEST_SPACE", "BSG_BI"), values.get("DSP_TEST_OBJECT_TYPE", "local-tables"),
        values.get("DSP_TEST_TECHNICAL_NAME", "T_TEST"))
    assert report["success"], report
