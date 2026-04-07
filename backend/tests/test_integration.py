"""
Testes de integração — fluxo completo HTTP + WebSocket.
Usa TestClient do FastAPI com AsyncClient para WebSocket.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import WSEventType


@pytest.fixture
def client():
    return TestClient(app)


# ─── Auth Integration ─────────────────────────────────────────────────────────

class TestAuthEndpoint:

    def test_login_success(self, client):
        resp = client.post("/auth/login", json={
            "email": "admin@noc.local",
            "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "admin@noc.local"
        assert data["user"]["profile"] in ["N1", "N2", "engineer", "manager"]

    def test_login_wrong_password(self, client):
        resp = client.post("/auth/login", json={
            "email": "admin@noc.local",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post("/auth/login", json={
            "email": "ghost@noc.local",
            "password": "any",
        })
        assert resp.status_code == 401

    def test_login_all_seed_users(self, client):
        users = [
            ("admin@noc.local", "admin123"),
            ("n1@noc.local",    "noc2024"),
            ("eng@noc.local",   "eng2024"),
            ("gestor@noc.local","mgr2024"),
        ]
        for email, password in users:
            resp = client.post("/auth/login", json={"email": email, "password": password})
            assert resp.status_code == 200, f"Login failed for {email}"
            assert resp.json()["token"]

    def test_token_contains_user_profile(self, client):
        resp = client.post("/auth/login", json={
            "email": "eng@noc.local", "password": "eng2024"
        })
        assert resp.json()["user"]["profile"] == "engineer"


# ─── Health Endpoint ──────────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        with patch("app.routers.health._dispatcher") as mock_dispatcher, \
             patch("app.routers.health.session_manager") as mock_sm:

            mock_sm.redis.ping = AsyncMock()
            mock_dispatcher.health_check = AsyncMock(return_value={"status": "ok"})

            resp = client.get("/health")
            assert resp.status_code == 200

    def test_health_structure(self, client):
        with patch("app.routers.health._dispatcher") as mock_dispatcher, \
             patch("app.routers.health.session_manager") as mock_sm:

            mock_sm.redis.ping = AsyncMock()
            mock_dispatcher.health_check = AsyncMock(return_value={"status": "ok"})

            data = client.get("/health").json()
            assert "status" in data
            assert "services" in data
            assert "timestamp" in data
            assert isinstance(data["services"], list)

    def test_health_includes_all_services(self, client):
        with patch("app.routers.health._dispatcher") as mock_dispatcher, \
             patch("app.routers.health.session_manager") as mock_sm:

            mock_sm.redis.ping = AsyncMock()
            mock_dispatcher.health_check = AsyncMock(return_value={"status": "ok"})

            data = client.get("/health").json()
            service_names = [s["name"] for s in data["services"]]
            assert "redis" in service_names
            for svc in ["zabbix", "datadog", "grafana", "thousandeyes"]:
                assert f"mcp-{svc}" in service_names


# ─── WebSocket Integration ────────────────────────────────────────────────────

class TestWebSocketAuth:

    def test_ws_rejected_without_token(self, client):
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises((WebSocketDisconnect, Exception)):
            with client.websocket_connect("/ws/chat") as ws:
                ws.receive_text()

    def test_ws_rejected_with_invalid_token(self, client):
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises((WebSocketDisconnect, Exception)):
            with client.websocket_connect("/ws/chat?token=invalid.token.here") as ws:
                ws.receive_text()

    def test_ws_accepted_with_valid_token(self, client):
        # Get valid token first
        token = client.post("/auth/login", json={
            "email": "admin@noc.local", "password": "admin123"
        }).json()["token"]

        with patch("app.websocket.handler.orchestrator") as mock_orch:
            async def mock_process(*args, **kwargs):
                from app.models import WSOutbound, WSEventType
                yield WSOutbound(type=WSEventType.agent_token, content="Olá")
                yield WSOutbound(type=WSEventType.agent_done)

            mock_orch.process_message = mock_process

            with patch("app.agent.session.session_manager") as mock_sm:
                mock_sm.get_session = AsyncMock(return_value=None)
                mock_sm.save_session = AsyncMock()

                with client.websocket_connect(f"/ws/chat?token={token}") as ws:
                    ws.send_text(json.dumps({
                        "type": "user_message",
                        "content": "Olá agente",
                        "sessionId": "test-session-1",
                    }))
                    events = []
                    for _ in range(2):
                        data = json.loads(ws.receive_text())
                        events.append(data)

                types = [e["type"] for e in events]
                assert "agent_token" in types
                assert "agent_done" in types


class TestWebSocketPingPong:

    def test_ping_returns_pong(self, client):
        token = client.post("/auth/login", json={
            "email": "admin@noc.local", "password": "admin123"
        }).json()["token"]

        with client.websocket_connect(f"/ws/chat?token={token}") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            resp = json.loads(ws.receive_text())
            assert resp["type"] == "pong"
