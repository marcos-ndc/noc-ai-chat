"""
Testes dos MCP Servers em modo mock (sem APIs reais configuradas).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os


def _add_mcp_path(svc: str):
    path = os.path.join(os.path.dirname(__file__), f"../../mcp-servers/{svc}")
    if path not in sys.path:
        sys.path.insert(0, path)


# ─── Zabbix MCP ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def zabbix_client():
    _add_mcp_path("zabbix")
    from server import app as zabbix_app
    async with AsyncClient(transport=ASGITransport(app=zabbix_app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestMCPZabbix:

    async def test_health_returns_ok_in_mock_mode(self, zabbix_client):
        resp = await zabbix_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body.get("mode") == "mock"

    async def test_get_active_alerts_returns_list(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_alerts", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "monitors" in body or isinstance(body, list)

    async def test_get_active_alerts_mock_contains_description(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_alerts", json={"severity": "high"})
        alerts = resp.json()
        assert all("description" in a for a in alerts)

    async def test_get_host_status_returns_data(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_host_status", json={"hostname": "web-01"})
        assert resp.status_code == 200

    async def test_get_trigger_history_returns_list(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_trigger_history",
                                        json={"hostname": "web-01", "hours": 24})
        assert resp.status_code == 200


# ─── Datadog MCP ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def datadog_client():
    _add_mcp_path("datadog")
    from server import app as datadog_app
    async with AsyncClient(transport=ASGITransport(app=datadog_app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestMCPDatadog:

    async def test_health_returns_ok_in_mock_mode(self, datadog_client):
        resp = await datadog_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_get_active_monitors_returns_list(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_active_monitors", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "monitors" in body or isinstance(body, list)

    async def test_get_monitors_contain_name_and_status(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_active_monitors", json={"status": "Alert"})
        monitors = resp.json()
        monitors = body.get("monitors", body) if isinstance(body, dict) else body
        assert all("name" in m for m in monitors)

    async def test_get_incidents_returns_data(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_incidents", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (dict, list))

    async def test_get_metrics_returns_response(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_metrics",
                                         json={"metric": "system.cpu.user"})
        assert resp.status_code == 200
        body = resp.json()
        assert "series" in body or "note" in body


# ─── Grafana MCP ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def grafana_client():
    _add_mcp_path("grafana")
    from server import app as grafana_app
    async with AsyncClient(transport=ASGITransport(app=grafana_app), base_url="http://test") as c:
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
        body = resp.json()
        assert isinstance(body, (dict, list))

    async def test_get_alert_rules_returns_list(self, grafana_client):
        resp = await grafana_client.post("/tools/grafana_get_alert_rules", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (list, dict))


# ─── ThousandEyes MCP ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def thousandeyes_client():
    _add_mcp_path("thousandeyes")
    from server import app as thousandeyes_app
    async with AsyncClient(transport=ASGITransport(app=thousandeyes_app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestMCPThousandEyes:

    async def test_health_returns_ok_in_mock_mode(self, thousandeyes_client):
        resp = await thousandeyes_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_get_active_alerts_returns_data(self, thousandeyes_client):
        resp = await thousandeyes_client.post("/tools/thousandeyes_get_active_alerts", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (dict, list))

    async def test_get_test_results_requires_test_id(self, thousandeyes_client):
        resp = await thousandeyes_client.post("/tools/thousandeyes_get_test_results", json={})
        # 422 = validation error (test_id required), which is correct behavior
        assert resp.status_code == 422

    async def test_get_test_results_with_valid_id(self, thousandeyes_client):
        resp = await thousandeyes_client.post("/tools/thousandeyes_get_test_results",
                                              json={"test_id": "12345"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (dict, list))
