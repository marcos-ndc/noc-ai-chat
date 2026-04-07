"""
Testes para os MCP servers Zabbix e Datadog — modo mock e real.
Em modo mock: valida estrutura de resposta e fallback.
Em modo real: valida com ZABBIX_URL / DATADOG_API_KEY no ambiente.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
async def zabbix_client():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../mcp-servers/zabbix"))
    # Force mock mode for tests
    os.environ.setdefault("ZABBIX_URL", "")
    from server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def datadog_client():
    import sys
    import importlib.util

    dd_path = os.path.join(os.path.dirname(__file__), "../../mcp-servers/datadog/server.py")
    os.environ.setdefault("DATADOG_API_KEY", "")

    # Force load from explicit path to avoid module cache collision with zabbix/server.py
    spec = importlib.util.spec_from_file_location("datadog_server", dd_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

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

    async def test_get_active_alerts_returns_list(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_alerts", json={})
        assert resp.status_code == 200
        alerts = resp.json()
        assert isinstance(alerts, list)
        assert len(alerts) > 0

    async def test_get_active_alerts_has_required_fields(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_alerts", json={})
        alerts = resp.json()
        for a in alerts:
            assert "description" in a
            assert "severity_label" in a
            assert "severity_int" in a
            assert "hosts" in a
            assert "duration_minutes" in a

    async def test_get_active_alerts_severity_filter(self, zabbix_client):
        resp = await zabbix_client.post(
            "/tools/zabbix_get_active_alerts",
            json={"severity": "high"}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_active_problems_returns_list(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_problems", json={})
        assert resp.status_code == 200
        problems = resp.json()
        assert isinstance(problems, list)

    async def test_get_active_problems_has_required_fields(self, zabbix_client):
        resp = await zabbix_client.post("/tools/zabbix_get_active_problems", json={})
        problems = resp.json()
        for p in problems:
            assert "severity_label" in p
            assert "acknowledged" in p
            assert "duration_minutes" in p

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
        assert body["mode"] == "mock"

    async def test_get_active_monitors_returns_data(self, datadog_client):
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
            assert "tags" in m

    async def test_get_active_monitors_with_tags_filter(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_active_monitors",
            json={"tags": ["env:prod"], "status": "Alert"}
        )
        assert resp.status_code == 200
        assert "monitors" in resp.json()

    async def test_get_metrics_returns_series(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_metrics",
            json={"metric": "system.cpu.user", "from_minutes_ago": 60}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "series" in body
        assert "query" in body

    async def test_get_metrics_series_has_stats(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_metrics",
            json={"metric": "system.cpu.user"}
        )
        series = resp.json()["series"]
        for s in series:
            assert "metric" in s
            assert "latest_value" in s
            assert "avg" in s

    async def test_get_incidents_returns_data(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_incidents", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "incidents" in body

    async def test_get_logs_returns_data(self, datadog_client):
        resp = await datadog_client.post(
            "/tools/datadog_get_logs",
            json={"query": "status:error", "from_minutes_ago": 30}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "logs" in body
        assert "query" in body

    async def test_get_hosts_returns_data(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_hosts", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert "hosts" in body
        assert body["count"] > 0

    async def test_get_hosts_has_required_fields(self, datadog_client):
        resp = await datadog_client.post("/tools/datadog_get_hosts", json={})
        hosts = resp.json()["hosts"]
        for h in hosts:
            assert "name" in h
            assert "status" in h
            assert "up" in h


# ─── Integration config validation ───────────────────────────────────────────

class TestIntegrationConfig:

    def test_zabbix_env_vars_documented(self):
        """Verifica que as env vars do Zabbix estão documentadas no .env.example."""
        env_example = open(
            os.path.join(os.path.dirname(__file__), "../../.env.example")
        ).read()
        assert "ZABBIX_URL" in env_example
        assert "ZABBIX_API_TOKEN" in env_example
        assert "ZABBIX_USER" in env_example
        assert "ZABBIX_PASSWORD" in env_example

    def test_datadog_env_vars_documented(self):
        """Verifica que as env vars do Datadog estão documentadas no .env.example."""
        env_example = open(
            os.path.join(os.path.dirname(__file__), "../../.env.example")
        ).read()
        assert "DATADOG_API_KEY" in env_example
        assert "DATADOG_APP_KEY" in env_example
        assert "DATADOG_SITE" in env_example

    def test_zabbix_mock_mode_without_url(self):
        """Zabbix MCP entra em modo mock quando ZABBIX_URL não está configurado."""
        import importlib
        import sys

        # Remove cached module
        for key in list(sys.modules.keys()):
            if "mcp-servers" in key or key == "server":
                del sys.modules[key]

        zabbix_path = os.path.join(
            os.path.dirname(__file__), "../../mcp-servers/zabbix"
        )
        if zabbix_path not in sys.path:
            sys.path.insert(0, zabbix_path)

        old_url = os.environ.get("ZABBIX_URL", "")
        os.environ["ZABBIX_URL"] = ""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "server_test", os.path.join(zabbix_path, "server.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert mod.MOCK_MODE is True
        finally:
            if old_url:
                os.environ["ZABBIX_URL"] = old_url
