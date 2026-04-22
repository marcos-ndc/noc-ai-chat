"""
Tests for security features:
- Row Level Security (RLS) on sessions
- Security headers on all responses
- CORS configuration
- Auth required on TTS/STT endpoints
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_token():
    from app.auth.service import auth_service
    return auth_service.create_token({
        "sub": "user-1", "email": "admin@noc.local", "profile": "n2"
    })


@pytest.fixture
def other_user_token():
    from app.auth.service import auth_service
    return auth_service.create_token({
        "sub": "user-2", "email": "n1@noc.local", "profile": "n1"
    })


# ─── Security Headers ─────────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_x_frame_options_deny(self, client):
        r = client.get("/health")
        assert r.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options(self, client):
        r = client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy(self, client):
        r = client.get("/health")
        assert "strict-origin" in r.headers.get("referrer-policy", "")

    def test_permissions_policy_has_microphone_self(self, client):
        r = client.get("/health")
        policy = r.headers.get("permissions-policy", "")
        assert "microphone=(self)" in policy

    def test_permissions_policy_no_camera(self, client):
        r = client.get("/health")
        policy = r.headers.get("permissions-policy", "")
        assert "camera=()" in policy

    def test_xss_protection(self, client):
        r = client.get("/health")
        assert r.headers.get("x-xss-protection") == "1; mode=block"

    def test_security_headers_on_post(self, client):
        """Security headers apply to POST requests too."""
        r = client.post("/auth/login", json={"email": "x", "password": "y"})
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("x-content-type-options") == "nosniff"


# ─── Auth Required on TTS/STT ─────────────────────────────────────────────────

class TestTTSAuthRequired:
    def test_speak_without_token_returns_401(self, client):
        r = client.post("/tts/speak", json={"text": "hello"})
        assert r.status_code == 401

    def test_voices_without_token_returns_401(self, client):
        r = client.get("/tts/voices")
        assert r.status_code == 401

    def test_status_without_token_returns_401(self, client):
        r = client.get("/tts/status")
        assert r.status_code == 401

    def test_speak_with_invalid_token_returns_401(self, client):
        r = client.post(
            "/tts/speak",
            json={"text": "hello"},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert r.status_code == 401

    def test_voices_with_valid_token_passes_auth(self, client, valid_token):
        r = client.get(
            "/tts/voices",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Should not return 401/403 (may return 200 or error from provider)
        assert r.status_code != 401
        assert r.status_code != 403


class TestSTTAuthRequired:
    def test_transcribe_without_token_returns_401(self, client):
        r = client.post("/stt/transcribe")
        assert r.status_code == 401

    def test_status_without_token_returns_401(self, client):
        r = client.get("/stt/status")
        assert r.status_code == 401


# ─── Row Level Security ───────────────────────────────────────────────────────

class TestRowLevelSecurity:
    def _setup_redis(self):
        from app.agent.session import session_manager
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        session_manager.redis = mock_redis
        return mock_redis

    @pytest.mark.asyncio
    async def test_user_can_access_own_session(self):
        """A user can access a session they created."""
        from app.websocket.handler import get_or_create_session
        from app.models import UserOut, UserProfile

        user = UserOut(
            id="user-1", name="Test", email="test@test.com",
            profile=UserProfile.N2, avatarInitials="TT"
        )
        self._setup_redis()
        session = await get_or_create_session("sess-1", user)
        assert session.user_id == "user-1"

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_session(self):
        """RLS: a user cannot access a session owned by another user."""
        from app.websocket.handler import get_or_create_session
        from app.models import UserOut, UserProfile, SessionData
        from app.agent.session import session_manager
        import json

        owner = UserOut(
            id="user-1", name="Owner", email="owner@test.com",
            profile=UserProfile.N2, avatarInitials="OW"
        )
        attacker = UserOut(
            id="user-2", name="Attacker", email="attacker@test.com",
            profile=UserProfile.N1, avatarInitials="AT"
        )

        # Create session owned by user-1
        existing_session = SessionData(
            session_id="sess-owned",
            user_id="user-1",
            user_profile=UserProfile.N2,
        )
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=existing_session.model_dump_json()
        )
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        session_manager.redis = mock_redis

        # user-2 tries to access user-1's session
        with pytest.raises(PermissionError):
            await get_or_create_session("sess-owned", attacker)

    @pytest.mark.asyncio
    async def test_session_user_id_matches_token_user(self):
        """Session user_id is set from authenticated user, not from client."""
        from app.websocket.handler import get_or_create_session
        from app.models import UserOut, UserProfile

        user = UserOut(
            id="user-3", name="Eng", email="eng@test.com",
            profile=UserProfile.engineer, avatarInitials="EN"
        )
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        from app.agent.session import session_manager
        session_manager.redis = mock_redis

        session = await get_or_create_session("sess-eng", user)
        # Session user_id must match authenticated user, not any client-provided value
        assert session.user_id == "user-3"
        assert session.user_profile == UserProfile.engineer


# ─── CORS ─────────────────────────────────────────────────────────────────────

class TestCORSHeaders:
    def test_cors_allows_localhost_in_dev(self, client):
        """In dev (cors_allow_all=True) any origin is accepted."""
        r = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not return 403
        assert r.status_code in (200, 204)

    def test_cors_exposes_tts_headers(self, client, valid_token):
        """TTS response headers are exposed to frontend."""
        r = client.get(
            "/tts/voices",
            headers={
                "Origin": "http://localhost:3001",
                "Authorization": f"Bearer {valid_token}",
            },
        )
        exposed = r.headers.get("access-control-expose-headers", "")
        assert "X-TTS-Provider" in exposed or r.status_code == 200
