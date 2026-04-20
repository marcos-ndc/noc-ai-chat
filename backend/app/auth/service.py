from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt, JWTError

from app.models import AuthResponse, UserOut, UserProfile
from app.settings import settings


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


# ─── Seed users (replace with DB in v2) ──────────────────────────────────────
_USERS: list[dict] = [
    {
        "id": "user-1",
        "name": "Admin NOC",
        "email": "admin@noc.local",
        "hashed_password": _hash_password("admin123"),
        "profile": UserProfile.N2,
    },
    {
        "id": "user-2",
        "name": "Analista N1",
        "email": "n1@noc.local",
        "hashed_password": _hash_password("noc2024"),
        "profile": UserProfile.N1,
    },
    {
        "id": "user-3",
        "name": "Engenheiro Sênior",
        "email": "eng@noc.local",
        "hashed_password": _hash_password("eng2024"),
        "profile": UserProfile.engineer,
    },
    {
        "id": "user-4",
        "name": "Gestor NOC",
        "email": "gestor@noc.local",
        "hashed_password": _hash_password("mgr2024"),
        "profile": UserProfile.manager,
    },
    {
        "id": "user-5",
        "name": "Admin Sistema",
        "email": "admin-sys@noc.local",
        "hashed_password": _hash_password("admin-noc-2024"),
        "profile": UserProfile.admin,
    },
]


class AuthService:
    def login(self, email: str, password: str) -> Optional[AuthResponse]:
        user = next((u for u in _USERS if u["email"] == email), None)
        if not user:
            return None
        if not _verify_password(password, user["hashed_password"]):
            return None

        payload = {
            "sub": user["id"],
            "email": user["email"],
            "profile": user["profile"].value,
        }
        token = self.create_token(payload)

        return AuthResponse(
            token=token,
            user=UserOut(
                id=user["id"],
                name=user["name"],
                email=user["email"],
                profile=user["profile"],
                avatarInitials=_initials(user["name"]),
            ),
        )

    def create_token(self, payload: dict) -> str:
        data = payload.copy()
        data["exp"] = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
        return jwt.encode(data, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        except JWTError as e:
            raise ValueError(f"Token invalid or expired: {e}") from e

    def get_user_from_token(self, token: str) -> Optional[UserOut]:
        try:
            payload = self.decode_token(token)
            user = next((u for u in _USERS if u["id"] == payload["sub"]), None)
            if not user:
                return None
            return UserOut(
                id=user["id"],
                name=user["name"],
                email=user["email"],
                profile=user["profile"],
                avatarInitials=_initials(user["name"]),
            )
        except ValueError:
            return None


auth_service = AuthService()
