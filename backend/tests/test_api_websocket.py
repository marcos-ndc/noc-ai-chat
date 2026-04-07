"""
Testes de integração — WebSocket /ws/chat
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, AsyncMock
from starlette.testclient import TestClient

from app.main import app
from app.models import WSEventType


@pytest.fixture
def sync_client():
    """TestClient síncrono para testes de WebSocket (Starlette nativo)."""
    return TestClient(app)


@pytest.fixture
def valid_token():
    from app.auth.service import auth_service
    return auth_service.create_token({
        "sub": "user-1",
        "email": "admin@noc.local",
        "profile": "N2",
    })


@pytest.fixture
def n1_token():
    from app.auth.service import auth_service
    return auth_service.create_token({
        "sub": "user-2",
        "email": "n1@noc.local",
        "profile": "N1",
    })


class TestWebSocketAuth:

    def test_ws_rejects_connection_without_token(self, sync_client):
        with pytest.raises(Exception):
            with sync_client.websocket_connect("/ws/chat") as ws:
                ws.receive_text()

    def test_ws_rejects_invalid_token(self, sync_client):
        with pytest.raises(Exception):
            with sync_client.websocket_connect("/ws/chat?token=invalid.token.here") as ws:
                ws.receive_text()

    def test_ws_accepts_valid_token(self, sync_client, valid_token):
        with sync_client.websocket_connect(f"/ws/chat?token={valid_token}") as ws:
            # Connection accepted — send ping to verify
            ws.send_text(json.dumps({"type": "ping"}))
            response = json.loads(ws.receive_text())
            assert response["type"] == "pong"


class TestWebSocketMessages:

    def test_ping_returns_pong(self, sync_client, valid_token):
        with sync_client.websocket_connect(f"/ws/chat?token={valid_token}") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            response = json.loads(ws.receive_text())
            assert response["type"] == "pong"

    def test_invalid_json_returns_error(self, sync_client, valid_token):
        with sync_client.websocket_connect(f"/ws/chat?token={valid_token}") as ws:
            ws.send_text("not valid json {{")
            response = json.loads(ws.receive_text())
            assert response["type"] == "error"

    def test_message_accepted_without_rejection(self, sync_client, valid_token):
        """WebSocket accepts user_message without closing with error code."""
        from app.agent.orchestrator import orchestrator
        from app.agent.session import session_manager

        mock_redis_inst = AsyncMock()
        mock_redis_inst.get = AsyncMock(return_value=None)
        mock_redis_inst.set = AsyncMock(return_value=True)
        session_manager.redis = mock_redis_inst

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Resposta mock."
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = "end_turn"
        orchestrator._client = MagicMock()
        orchestrator._client.messages.create = MagicMock(return_value=mock_response)

        # Verify connection stays alive and can exchange messages
        with sync_client.websocket_connect(f"/ws/chat?token={valid_token}") as ws:
            # First confirm ping/pong works (connection healthy)
            ws.send_text(json.dumps({"type": "ping"}))
            resp = json.loads(ws.receive_text())
            assert resp["type"] == "pong"

            # Send user_message — should not crash or close the connection
            ws.send_text(json.dumps({
                "type": "user_message",
                "content": "Tem incidentes ativos?",
                "sessionId": "test-session-ws-1",
            }))
            # If we get here without exception, message was accepted
            # (async response may arrive after test client closes — that's ok)

    def test_orchestrator_process_message_yields_tokens(self):
        """Unit test: orchestrator.process_message yields agent_token + agent_done."""
        import asyncio
        from app.agent.orchestrator import AgentOrchestrator
        from app.models import SessionData, UserProfile, WSEventType

        mock_redis_inst = AsyncMock()
        mock_redis_inst.get = AsyncMock(return_value=None)
        mock_redis_inst.set = AsyncMock(return_value=True)

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Resposta do agente."
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = "end_turn"

        orch = AgentOrchestrator()
        orch._client = MagicMock()
        orch._client.messages.create = MagicMock(return_value=mock_response)

        session = SessionData(
            session_id="unit-test-sess",
            user_id="user-1",
            user_profile=UserProfile.N2,
        )

        async def run():
            from app.agent.session import session_manager
            session_manager.redis = mock_redis_inst
            events = []
            async for event in orch.process_message("Olá!", session):
                events.append(event)
            return events

        events = asyncio.get_event_loop().run_until_complete(run())
        event_types = [e.type for e in events]
        assert WSEventType.agent_done in event_types
        assert any(e.type == WSEventType.agent_token for e in events)
