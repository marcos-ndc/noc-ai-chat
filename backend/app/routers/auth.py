from fastapi import APIRouter, HTTPException, status
from app.models import AuthRequest, AuthResponse
from app.auth.service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(body: AuthRequest):
    result = auth_service.login(body.email, body.password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    return result
