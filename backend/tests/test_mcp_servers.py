"""
Testes dos MCP Servers em modo mock (sem APIs reais configuradas).
Valida estrutura de resposta, fallback mock e comportamento esperado.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os
import importlib.util


def _load_mcp_server(svc: str):
    """Load a MCP server module from its path, avoiding sys.path collisions."""
    path = os.path.join(os.path.dirname(__file__), f"../../mcp-servers/{svc}/server.py")
    spec = importlib.util.spec_from_file_location(f"mcp_{svc}_server", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── Zabbix MCP ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def zabbix_client():
    mod = _load_mcp_server("zabbix")
    async with AsyncClient(transport=ASGITransport(app=mod.app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestMCPZabbix:

    async def test_health_returns_ok_in_mock_mode(self, zabbix_client):
        resp = await zabbix_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body.get("mode") == "mock"

    async def test_get_active_alerts_returns_envelope(self, zabbix_client):
        """Alerts now return {count, alerts, organization} envelope."""
        resp = await zabbix_client.post("/tools/zabbix_get_active_alerts", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "alerts" in body
        assert "count" in body
        assert body["count"] > 0

    async def test_get_active_alerts_items_have_required_fields(self, zabbix_client):
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
        """Problems return {count, problems, organization} envelope."""
        resp = await zabbix_client.post("/tools/zabbix_get_active_problems", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "problems" in body
        assert "count" in body

    async def test_get_active_problems_items_have_required_fields(self, zabbix_client):
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
        assert body["total_organizations"] > 0

    async def test_get_organization_summary_returns_data(self, zabbix_client):
        resp = await zabbix_client.post(
            "/tools/zabbix_get_organization_summary",
            json={"organization": "ClienteA"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("found") is True
        assert "health_status" in body
        assert "hosts" in body
        assert "problems" in body

    async def test_get_host_status_returns_data(self, zabbix_client):
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


# ─── Datadog MCP ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def datadog_client():
    mod = _load_mcp_server("datadog")
    async with AsyncClient(transport=ASGITransport(app=mod.app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestMCPDatadog:

    async def test_health_returns_ok_in_mock_mode(self, datadog_client):
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

    async def test_get_active_monitors_items_have_fields(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_active_monitors", json={})
        monitors = resp.json()["monitors"]
        for m in monitors:
            assert "name" in m
            assert "status" in m

    async def test_get_incidents_returns_envelope(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_incidents", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (dict, list))

    async def test_get_metrics_returns_response(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_metrics",
            json={"metric": "system.cpu.user"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (dict, list))

    async def test_get_logs_returns_response(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_logs",
            json={"query": "status:error"}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))

    async def test_get_hosts_returns_response(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_hosts", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))


# ─── Grafana MCP ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def grafana_client():
    mod = _load_mcp_server("grafana")
    async with AsyncClient(transport=ASGITransport(app=mod.app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestMCPGrafana:

    async def test_health_returns_ok_in_mock_mode(self, grafana_client):
        resp = await grafana_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_get_firing_alerts_returns_data(self, grafana_client):
        resp = await grafana_client.post("/tools/grafana_get_firing_alerts", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))

    async def test_get_alert_rules_returns_data(self, grafana_client):
        resp = await grafana_client.post("/tools/grafana_get_alert_rules", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), (dict, list))


# ─── ThousandEyes MCP ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def thousandeyes_client():
    mod = _load_mcp_server("thousandeyes")
    async with AsyncClient(transport=ASGITransport(app=mod.app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestMCPThousandEyes:

    async def test_health_returns_ok_in_mock_mode(self, thousandeyes_client):
        resp = await thousandeyes_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_list_tests_returns_envelope(self, thousandeyes_client):
        resp = await thousandeyes_client.post("/tools/thousandeyes_list_tests", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "tests" in body
        assert "count" in body

    async def test_get_active_alerts_returns_envelope(self, thousandeyes_client):
        resp = await thousandeyes_client.post(
            "/tools/thousandeyes_get_active_alerts", json={}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "alerts" in body
        assert "count" in body

    async def test_get_test_results_requires_test_id(self, thousandeyes_client):
        resp = await thousandeyes_client.post(
            "/tools/thousandeyes_get_test_results", json={}
        )
        assert resp.status_code == 422  # validation error — test_id required

    async def test_get_test_results_mock_returns_data(self, thousandeyes_client):
        resp = await thousandeyes_client.post(
            "/tools/thousandeyes_get_test_results",
            json={"test_id": "12345"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "aggregated" in body
        assert "testId" in body

    async def test_get_test_availability_returns_envelope(self, thousandeyes_client):
        resp = await thousandeyes_client.post(
            "/tools/thousandeyes_get_test_availability", json={}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "all_tests" in body
        assert "total_tests" in body

    async def test_get_bgp_alerts_returns_envelope(self, thousandeyes_client):
        resp = await thousandeyes_client.post(
            "/tools/thousandeyes_get_bgp_alerts", json={}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "bgp_alerts" in body

    async def test_get_agents_returns_envelope(self, thousandeyes_client):
        resp = await thousandeyes_client.post(
            "/tools/thousandeyes_get_agents", json={}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "enterprise" in body
        assert "cloud" in body
        assert "total" in body
