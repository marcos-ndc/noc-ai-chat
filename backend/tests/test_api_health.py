"""
Testes de integração — GET /health
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
class TestHealthEndpoint:

    async def test_health_returns_200(self, client: AsyncClient):
        with patch("app.routers.health._dispatcher") as mock_disp, \
             patch("app.routers.health.session_manager") as mock_sm:
            mock_sm.redis.ping = AsyncMock(return_value=True)
            mock_disp.health_check = AsyncMock(return_value={"status": "ok"})

            resp = await client.get("/health")
            assert resp.status_code == 200

    async def test_health_returns_status_field(self, client: AsyncClient):
        with patch("app.routers.health._dispatcher") as mock_disp, \
             patch("app.routers.health.session_manager") as mock_sm:
            mock_sm.redis.ping = AsyncMock(return_value=True)
            mock_disp.health_check = AsyncMock(return_value={"status": "ok"})

            resp = await client.get("/health")
            body = resp.json()
            assert "status" in body
            assert body["status"] in ("ok", "degraded", "down")

    async def test_health_lists_all_services(self, client: AsyncClient):
        with patch("app.routers.health._dispatcher") as mock_disp, \
             patch("app.routers.health.session_manager") as mock_sm:
            mock_sm.redis.ping = AsyncMock(return_value=True)
            mock_disp.health_check = AsyncMock(return_value={"status": "ok"})

            resp = await client.get("/health")
            services = {s["name"] for s in resp.json()["services"]}
            assert "redis" in services
            assert "mcp-zabbix" in services
            assert "mcp-datadog" in services
            assert "mcp-grafana" in services
            assert "mcp-thousandeyes" in services

    async def test_health_degraded_when_redis_down(self, client: AsyncClient):
        with patch("app.routers.health._dispatcher") as mock_disp, \
             patch("app.routers.health.session_manager") as mock_sm:
            mock_sm.redis.ping = AsyncMock(side_effect=ConnectionError("Redis down"))
            mock_disp.health_check = AsyncMock(return_value={"status": "ok"})

            resp = await client.get("/health")
            body = resp.json()
            redis_svc = next(s for s in body["services"] if s["name"] == "redis")
            assert redis_svc["status"] == "down"

    async def test_health_includes_timestamp(self, client: AsyncClient):
        with patch("app.routers.health._dispatcher") as mock_disp, \
             patch("app.routers.health.session_manager") as mock_sm:
            mock_sm.redis.ping = AsyncMock(return_value=True)
            mock_disp.health_check = AsyncMock(return_value={"status": "ok"})

            resp = await client.get("/health")
            assert "timestamp" in resp.json()

    async def test_health_redis_latency_reported(self, client: AsyncClient):
        with patch("app.routers.health._dispatcher") as mock_disp, \
             patch("app.routers.health.session_manager") as mock_sm:
            mock_sm.redis.ping = AsyncMock(return_value=True)
            mock_disp.health_check = AsyncMock(return_value={"status": "ok"})

            resp = await client.get("/health")
            redis_svc = next(s for s in resp.json()["services"] if s["name"] == "redis")
            assert "latency_ms" in redis_svc
            assert redis_svc["latency_ms"] >= 0
