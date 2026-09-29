from datasphere_mcp.config import Settings, TenantConfig
from datasphere_mcp.models.common import Environment
from datasphere_mcp.runtime import Runtime


async def test_environment_clients_and_token_caches_are_isolated():
    runtime = Runtime(Settings(_env_file=None,
        dev=TenantConfig(base_url="https://dev.example"), qas=TenantConfig(base_url="https://qas.example")))
    try:
        dev = runtime.services(Environment.DEV)
        qas = runtime.services(Environment.QAS)
        assert dev is runtime.services(Environment.DEV)
        assert dev.objects.adapter is not qas.objects.adapter
        assert dev.objects.adapter.auth.cache is not qas.objects.adapter.auth.cache
        assert dev.objects.adapter.tenant.base_url == "https://dev.example"
        assert qas.objects.adapter.tenant.base_url == "https://qas.example"
    finally:
        await runtime.close()
    assert not runtime._clients
