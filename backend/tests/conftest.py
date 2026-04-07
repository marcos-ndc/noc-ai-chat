"""
Fixtures globais para testes de integração do NOC AI Chat backend.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models import UserProfile, SessionData


# ─── App client ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    """HTTP test client para o FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


# ─── Auth helpers ────────────────────────────────────────────────────────────

@pytest.fixture
def valid_credentials():
    return {"email": "admin@noc.local", "password": "admin123"}

@pytest.fixture
def invalid_credentials():
    return {"email": "admin@noc.local", "password": "wrong"}

@pytest.fixture
def unknown_user_credentials():
    return {"email": "nobody@noc.local", "password": "any"}

@pytest_asyncio.fixture
async def auth_token(client, valid_credentials):
    """Retorna token JWT válido para uso nos testes."""
    resp = await client.post("/auth/login", json=valid_credentials)
    return resp.json()["token"]

@pytest_asyncio.fixture
async def n1_token(client):
    resp = await client.post("/auth/login", json={"email": "n1@noc.local", "password": "noc2024"})
    return resp.json()["token"]

@pytest_asyncio.fixture
async def engineer_token(client):
    resp = await client.post("/auth/login", json={"email": "eng@noc.local", "password": "eng2024"})
    return resp.json()["token"]


# ─── Redis mock ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Mock do Redis para testes sem servidor real."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_redis_with_session(mock_redis):
    """Redis mock com sessão pré-populada."""
    session = SessionData(
        session_id="test-session",
        user_id="user-1",
        user_profile=UserProfile.N2,
    )
    mock_redis.get = AsyncMock(return_value=session.model_dump_json())
    return mock_redis


# ─── MCP dispatcher mock ─────────────────────────────────────────────────────

@pytest.fixture
def mock_mcp_dispatcher():
    """Mock do MCPDispatcher — evita chamadas reais aos MCP servers."""
    dispatcher = AsyncMock()
    dispatcher.call = AsyncMock(return_value={
        "data": [{"id": "mock-1", "description": "Mock alert", "severity": "high"}]
    })
    dispatcher.health_check = AsyncMock(return_value={"status": "ok"})
    return dispatcher


# ─── Claude API mock ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_claude_response():
    """Simula resposta do Claude API sem chamar a API real."""
    block = MagicMock()
    block.type = "text"
    block.text = "Não há incidentes críticos ativos no momento."

    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    return response
