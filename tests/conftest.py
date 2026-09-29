import os

import pytest

from datasphere_mcp.config import Settings


@pytest.fixture
def settings():
    return Settings(_env_file=None, mock_mode=True)


@pytest.fixture(autouse=True)
def isolate_unit_configuration(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return
    for key in list(os.environ):
        if key.startswith("DSP_"):
            monkeypatch.delenv(key)
