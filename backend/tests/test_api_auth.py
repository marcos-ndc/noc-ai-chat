"""
Testes de integração — POST /auth/login
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthEndpoint:

    async def test_login_success_returns_200(self, client: AsyncClient, valid_credentials):
        resp = await client.post("/auth/login", json=valid_credentials)
        assert resp.status_code == 200

    async def test_login_success_returns_token(self, client: AsyncClient, valid_credentials):
        resp = await client.post("/auth/login", json=valid_credentials)
        body = resp.json()
        assert "token" in body
        assert len(body["token"]) > 20

    async def test_login_success_returns_user(self, client: AsyncClient, valid_credentials):
        resp = await client.post("/auth/login", json=valid_credentials)
        user = resp.json()["user"]
        assert user["email"] == valid_credentials["email"]
        assert "id" in user
        assert "name" in user
        assert "profile" in user
        assert "avatarInitials" in user

    async def test_login_invalid_password_returns_401(self, client: AsyncClient, invalid_credentials):
        resp = await client.post("/auth/login", json=invalid_credentials)
        assert resp.status_code == 401

    async def test_login_unknown_user_returns_401(self, client: AsyncClient, unknown_user_credentials):
        resp = await client.post("/auth/login", json=unknown_user_credentials)
        assert resp.status_code == 401

    async def test_login_missing_email_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={"password": "admin123"})
        assert resp.status_code == 422

    async def test_login_missing_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={"email": "admin@noc.local"})
        assert resp.status_code == 422

    async def test_login_empty_body_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={})
        assert resp.status_code == 422

    async def test_all_user_profiles_can_login(self, client: AsyncClient):
        users = [
            ("admin@noc.local", "admin123", "admin"),
            ("n1@noc.local", "noc2024", "N1"),
            ("eng@noc.local", "eng2024", "engineer"),
            ("gestor@noc.local", "mgr2024", "manager"),
        ]
        for email, password, expected_profile in users:
            resp = await client.post("/auth/login", json={"email": email, "password": password})
            assert resp.status_code == 200, f"Login falhou para {email}"
            assert resp.json()["user"]["profile"] == expected_profile

    async def test_login_token_is_valid_jwt(self, client: AsyncClient, valid_credentials):
        resp = await client.post("/auth/login", json=valid_credentials)
        token = resp.json()["token"]

        from app.auth.service import auth_service
        decoded = auth_service.decode_token(token)
        assert decoded["email"] == valid_credentials["email"]

    async def test_avatar_initials_format(self, client: AsyncClient, valid_credentials):
        resp = await client.post("/auth/login", json=valid_credentials)
        initials = resp.json()["user"]["avatarInitials"]
        assert len(initials) >= 1
        assert initials.isupper()
