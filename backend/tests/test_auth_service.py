import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.auth.service import AuthService
from app.models import UserProfile


@pytest.fixture
def auth_service():
    return AuthService()


class TestAuthService:

    def test_login_returns_token_and_user_for_valid_credentials(self, auth_service):
        result = auth_service.login("admin@noc.local", "admin123")
        assert result is not None
        assert result.token
        assert result.user.email == "admin@noc.local"

    def test_login_returns_none_for_invalid_password(self, auth_service):
        result = auth_service.login("admin@noc.local", "wrong-password")
        assert result is None

    def test_login_returns_none_for_unknown_user(self, auth_service):
        result = auth_service.login("unknown@noc.local", "any-password")
        assert result is None

    def test_jwt_encode_decode_roundtrip(self, auth_service):
        payload = {"sub": "user-1", "email": "test@noc.local", "profile": "N1"}
        token = auth_service.create_token(payload)
        decoded = auth_service.decode_token(token)
        assert decoded["sub"] == "user-1"
        assert decoded["email"] == "test@noc.local"

    def test_expired_token_raises(self, auth_service):
        payload = {"sub": "user-1", "email": "test@noc.local", "profile": "N1"}
        # Create token that already expired
        from jose import jwt
        from app.settings import settings
        expired_payload = {**payload, "exp": datetime.now(timezone.utc) - timedelta(hours=1)}
        token = jwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(Exception, match="expired|invalid"):
            auth_service.decode_token(token)

    def test_invalid_token_raises(self, auth_service):
        with pytest.raises(Exception):
            auth_service.decode_token("not.a.valid.token")

    def test_user_profile_is_correct(self, auth_service):
        result = auth_service.login("admin@noc.local", "admin123")
        assert result is not None
        assert result.user.profile in [p.value for p in UserProfile]

    def test_avatar_initials_generated(self, auth_service):
        result = auth_service.login("admin@noc.local", "admin123")
        assert result is not None
        assert len(result.user.avatarInitials) >= 1
