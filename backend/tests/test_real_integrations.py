"""
Testes de integração para MCP servers (modo mock) e validações de config.
Testa estrutura das respostas, modo mock automático e env vars documentadas.
"""
import os
import pytest
import pytest_asyncio
import importlib.util
from httpx import AsyncClient, ASGITransport


def _load_server(svc: str):
    path = os.path.join(os.path.dirname(__file__), f"../../mcp-servers/{svc}/server.py")
    spec = importlib.util.spec_from_file_location(f"integ_{svc}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest_asyncio.fixture
async def zabbix_client():
    mod = _load_server("zabbix")
    async with AsyncClient(transport=ASGITransport(app=mod.app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def datadog_client():
    mod = _load_server("datadog")
    async with AsyncClient(transport=ASGITransport(app=mod.app), base_url="http://test") as c:
        yield c


# ─── Zabbix MCP Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestZabbixMCPMockMode:

    async def test_health_ok_mock(self, zabbix_client):
        resp = await zabbix_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["mode"] == "mock"

    async def test_get_active_alerts_returns_envelope(self, zabbix_client):
        """Alerts return {count, alerts, organization} — not a bare list."""
        resp = await zabbix_client.post("/tools/zabbix_get_active_alerts", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "alerts" in body
        assert "count" in body
        assert isinstance(body["alerts"], list)
        assert body["count"] > 0

    async def test_get_active_alerts_has_required_fields(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_alerts", json={})
        alerts = resp.json()["alerts"]
        for a in alerts:
            assert "description" in a
            assert "severity_label" in a
            assert "hosts" in a
            assert "duration_minutes" in a

    async def test_get_active_alerts_organization_filter(self, zabbix_client):
        resp = await zabbix_client.post(
            "/tools/zabbix_get_active_alerts",
            json={"organization": "ClienteA"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "alerts" in body
        assert body.get("organization") == "ClienteA"

    async def test_get_active_problems_returns_envelope(self, zabbix_client):
        """Problems return {count, problems, organization} — not a bare list."""
        resp = await zabbix_client.post("/tools/zabbix_get_active_problems", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "problems" in body
        assert "count" in body
        assert isinstance(body["problems"], list)

    async def test_get_active_problems_has_required_fields(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_problems", json={})
        problems = resp.json()["problems"]
        for p in problems:
            assert "severity_label" in p
            assert "acknowledged" in p
            assert "duration_minutes" in p

    async def test_list_organizations_returns_envelope(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_list_organizations", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "organizations" in body
        assert "total_organizations" in body
        assert isinstance(body["organizations"], list)

    async def test_get_organization_summary(self, zabbix_client):
        resp = await zabbix_client.post(
            "/tools/zabbix_get_organization_summary",
            json={"organization": "ClienteA"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["found"] is True
        assert "health_status" in body
        assert "hosts" in body
        assert "problems" in body
        assert body["health_status"] in ("OK", "WARNING", "HIGH", "CRITICAL")

    async def test_get_host_status_found(self, zabbix_client):
        resp = await zabbix_client.post(
            "/tools/zabbix_get_host_status",
            json={"hostname": "web-server-01"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("found") is True
        assert "available_label" in body

    async def test_get_host_groups_returns_list(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_host_groups", json={})
        assert resp.status_code == 200
        groups = resp.json()
        assert isinstance(groups, list)
        assert len(groups) > 0
        assert all("name" in g for g in groups)

    async def test_get_trigger_history_returns_list(self, zabbix_client):
        resp = await zabbix_client.post(
            "/tools/zabbix_get_trigger_history",
            json={"hostname": "web-01", "hours": 24}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_item_latest_mock(self, zabbix_client):
        resp = await zabbix_client.post(
            "/tools/zabbix_get_item_latest",
            json={"hostname": "web-01", "item_key": "system.cpu.util"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "value" in body or "found" in body


# ─── Datadog MCP Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDatadogMCPMockMode:

    async def test_health_ok_mock(self, datadog_client):
        resp = await datadog_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body.get("mode") == "mock"

    async def test_get_active_monitors_returns_envelope(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_active_monitors", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "monitors" in body
        assert "count" in body
        assert body["count"] > 0

    async def test_get_active_monitors_has_required_fields(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_active_monitors", json={})
        monitors = resp.json()["monitors"]
        for m in monitors:
            assert "id" in m
            assert "name" in m
            assert "status" in m

    async def test_get_incidents_returns_data(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_incidents", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))

    async def test_get_metrics_returns_response(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_metrics",
            json={"metric": "system.cpu.user"}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))

    async def test_get_logs_returns_data(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_logs",
            json={"query": "status:error"}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))

    async def test_get_hosts_returns_data(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_hosts", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))


# ─── Config validation ────────────────────────────────────────────────────────

class TestIntegrationConfig:

    def test_zabbix_env_vars_documented(self):
        env_example = open(
            os.path.join(os.path.dirname(__file__), "../../.env.example")
        ).read()
        assert "ZABBIX_URL" in env_example
        assert "ZABBIX_API_TOKEN" in env_example

    def test_datadog_env_vars_documented(self):
        env_example = open(
            os.path.join(os.path.dirname(__file__), "../../.env.example")
        ).read()
        assert "DATADOG_API_KEY" in env_example
        assert "DATADOG_APP_KEY" in env_example

    def test_thousandeyes_env_vars_documented(self):
        env_example = open(
            os.path.join(os.path.dirname(__file__), "../../.env.example")
        ).read()
        assert "THOUSANDEYES_TOKEN" in env_example

    def test_openai_tts_env_vars_documented(self):
        env_example = open(
            os.path.join(os.path.dirname(__file__), "../../.env.example")
        ).read()
        assert "OPENAI_API_KEY" in env_example
        assert "TTS_VOICE" in env_example

    def test_zabbix_mock_mode_without_url(self):
        """Zabbix MCP entra em modo mock quando ZABBIX_URL não está configurado."""
        # Module is already loaded without ZABBIX_URL in test env
        mod = _load_server("zabbix")
        # MOCK_MODE is set at import time based on env vars
        # In test environment ZABBIX_URL is not set → MOCK_MODE should be True
        assert mod.MOCK_MODE is True, "Zabbix should be in mock mode without ZABBIX_URL"

    def test_datadog_mock_mode_without_key(self):
        """Datadog MCP entra em modo mock quando DATADOG_API_KEY não está configurado."""
        mod = _load_server("datadog")
        assert mod.MOCK_MODE is True, "Datadog should be in mock mode without DATADOG_API_KEY" 
