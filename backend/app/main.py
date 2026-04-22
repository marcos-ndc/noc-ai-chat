from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.tts import router as tts_router
from app.routers.stt import router as stt_router
from app.routers.admin import router as admin_router
from app.websocket.handler import handle_chat_websocket
from app.settings import settings

# ─── Structured logging ───────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()


# ─── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate critical configuration on startup
    key = settings.anthropic_api_key
    if not key:
        log.warning(
            "noc_ai_chat.config_warning",
            message="ANTHROPIC_API_KEY não configurada — o agente não conseguirá responder. "
                    "Adicione sua chave no arquivo .env na raiz do projeto e reinicie com 'make dev'.",
        )
    else:
        # Log masked key so we can confirm it's being loaded
        masked = key[:8] + "..." + key[-4:]
        log.info("noc_ai_chat.started", model=settings.claude_model, api_key_loaded=masked)
    yield
    log.info("noc_ai_chat.stopped")


# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NOC AI Chat API",
    version="1.0.0",
    description="Backend do agente de IA especializado em operações NOC",
    lifespan=lifespan,
)

# ─── Security Headers Middleware ─────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adiciona security headers a todas as respostas HTTP."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy — restrict browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), payment=(), usb=(), "
            "microphone=(self)"   # only self — required for voice input
        )
        # Content Security Policy
        if not settings.cors_allow_all:
            origins = " ".join(settings.cors_origins)
            response.headers["Content-Security-Policy"] = (
                f"default-src 'self'; "
                f"connect-src 'self' {origins} wss: ws:; "
                f"script-src 'self' 'unsafe-inline'; "
                f"style-src 'self' 'unsafe-inline'; "
                f"img-src 'self' data:; "
                f"media-src 'self' blob:; "
                f"font-src 'self' data:"
            )
        # HSTS — only in production (HTTPS)
        if not settings.cors_allow_all:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Dev:  CORS_ALLOW_ALL=true  → aceita qualquer origem (padrão)
# Prod: CORS_ALLOW_ALL=false → usa lista explícita de CORS_ORIGINS
#
# Exemplo .env produção:
#   CORS_ALLOW_ALL=false
#   CORS_ORIGINS=["https://noc.suaempresa.com","https://app.suaempresa.com"]

_origins    = ["*"] if settings.cors_allow_all else settings.cors_origins
_creds      = not settings.cors_allow_all   # credentials não funciona com wildcard
_methods    = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
_hdr_allow  = ["Authorization", "Content-Type", "Accept", "X-Requested-With"]
_hdr_expose = ["X-TTS-Provider", "X-TTS-Voice", "X-TTS-Model", "X-Generation-Id"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=_methods,
    allow_headers=_hdr_allow,
    expose_headers=_hdr_expose,
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(tts_router)
app.include_router(stt_router)
app.include_router(admin_router)


# ─── WebSocket ───────────────────────────────────────────────────────────────
@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await handle_chat_websocket(websocket)


# ─── Debug (dev only — disabled in production) ───────────────────────────────
@app.get("/debug/config")
async def debug_config():
    """Shows masked config values — only available in dev (CORS_ALLOW_ALL=true)."""
    if not settings.cors_allow_all:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=404, detail="Not found")
    import os
    key = settings.anthropic_api_key
    return {
        "anthropic_api_key": (key[:8] + "...[masked]") if key else "NOT SET",
        "anthropic_key_length": len(key),
        "claude_model": settings.claude_model,
        "cors_allow_all": settings.cors_allow_all,
        "redis_url": settings.redis_url,
        "env_ANTHROPIC_API_KEY_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }
