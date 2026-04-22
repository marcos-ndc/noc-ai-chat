"""
Shared FastAPI dependencies for authentication and authorization.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.service import auth_service
from app.models import UserOut, UserProfile

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserOut:
    """Require a valid JWT — returns the authenticated user."""
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação obrigatório",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = auth_service.get_user_from_token(creds.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserOut:
    """Require a valid JWT with admin profile."""
    user = get_current_user(creds)
    if user.profile != UserProfile.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return user
