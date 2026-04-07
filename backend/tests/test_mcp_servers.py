"""
Testes de integração — MCP Servers (modo mock, sem APIs reais)
"""
import pytest
from httpx import AsyncClient, ASGITransport


# ─── Zabbix MCP ──────────────────────────────────────────────────────────────

@pytest.fixture
def zabbix_client():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../mcp-servers/zabbix"))
    from server import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
class TestMCPZabbix:

    async def test_health_returns_ok_in_mock_mode(self, zabbix_client):
        async with zabbix_client as c:
            resp = await c.get("/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ok"
            assert body.get("mode") == "mock"

    async def test_get_active_alerts_returns_list(self, zabbix_client):
        async with zabbix_client as c:
            resp = await c.post("/tools/zabbix_get_active_alerts", json={})
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body, list)
            assert len(body) > 0

    async def test_get_active_alerts_mock_contains_description(self, zabbix_client):
        async with zabbix_client as c:
            resp = await c.post("/tools/zabbix_get_active_alerts", json={"severity": "high"})
            alerts = resp.json()
            assert all("description" in a for a in alerts)

    async def test_get_host_status_returns_data(self, zabbix_client):
        async with zabbix_client as c:
            resp = await c.post("/tools/zabbix_get_host_status", json={"hostname": "web-01"})
            assert resp.status_code == 200

    async def test_get_trigger_history_returns_list(self, zabbix_client):
        async with zabbix_client as c:
            resp = await c.post("/tools/zabbix_get_trigger_history",
                                json={"hostname": "web-01", "hours": 24})
            assert resp.status_code == 200


# ─── Datadog MCP ─────────────────────────────────────────────────────────────

@pytest.fixture
def datadog_client():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../mcp-servers/datadog"))
    from server import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
class TestMCPDatadog:

    async def test_health_returns_ok_in_mock_mode(self, datadog_client):
        async with datadog_client as c:
            resp = await c.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    async def test_get_active_monitors_returns_list(self, datadog_client):
        async with datadog_client as c:
            resp = await c.post("/tools/datadog_get_active_monitors", json={})
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body, list)
            assert len(body) > 0

    async def test_get_monitors_contain_name_and_status(self, datadog_client):
        async with datadog_client as c:
            resp = await c.post("/tools/datadog_get_active_monitors", json={"status": "Alert"})
            monitors = resp.json()
            assert all("name" in m and "status" in m for m in monitors)

    async def test_get_incidents_returns_data(self, datadog_client):
        async with datadog_client as c:
            resp = await c.post("/tools/datadog_get_incidents", json={})
            assert resp.status_code == 200
            assert "data" in resp.json()

    async def test_get_metrics_returns_series(self, datadog_client):
        async with datadog_client as c:
            resp = await c.post("/tools/datadog_get_metrics",
                                json={"metric": "system.cpu.user", "host": "web-01"})
            assert resp.status_code == 200


# ─── Grafana MCP ─────────────────────────────────────────────────────────────

@pytest.fixture
def grafana_client():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../mcp-servers/grafana"))
    from server import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
class TestMCPGrafana:

    async def test_health_returns_ok_in_mock_mode(self, grafana_client):
        async with grafana_client as c:
            resp = await c.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    async def test_get_firing_alerts_returns_data(self, grafana_client):
        async with grafana_client as c:
            resp = await c.post("/tools/grafana_get_firing_alerts", json={})
            assert resp.status_code == 200

    async def test_get_alert_rules_returns_list(self, grafana_client):
        async with grafana_client as c:
            resp = await c.post("/tools/grafana_get_alert_rules", json={})
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)


# ─── ThousandEyes MCP ────────────────────────────────────────────────────────

@pytest.fixture
def thousandeyes_client():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../mcp-servers/thousandeyes"))
    from server import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
class TestMCPThousandEyes:

    async def test_health_returns_ok_in_mock_mode(self, thousandeyes_client):
        async with thousandeyes_client as c:
            resp = await c.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    async def test_get_active_alerts_returns_data(self, thousandeyes_client):
        async with thousandeyes_client as c:
            resp = await c.post("/tools/thousandeyes_get_active_alerts", json={})
            assert resp.status_code == 200
            body = resp.json()
            assert "alerts" in body

    async def test_get_test_results_requires_test_id(self, thousandeyes_client):
        async with thousandeyes_client as c:
            # Missing required field
            resp = await c.post("/tools/thousandeyes_get_test_results", json={})
            assert resp.status_code == 422

    async def test_get_test_results_with_valid_id(self, thousandeyes_client):
        async with thousandeyes_client as c:
            resp = await c.post("/tools/thousandeyes_get_test_results",
                                json={"test_id": "test-123"})
            assert resp.status_code == 200
            body = resp.json()
            assert "test" in body and "results" in body
