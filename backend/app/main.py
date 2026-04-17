from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.tts import router as tts_router
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

# Em dev (cors_allow_all=True) aceita qualquer origem
# Em prod define CORS_ALLOW_ALL=false e CORS_ORIGINS no .env
_origins = ["*"] if settings.cors_allow_all else settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=not settings.cors_allow_all,  # credentials não funciona com *
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(tts_router)


# ─── WebSocket ───────────────────────────────────────────────────────────────
@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await handle_chat_websocket(websocket)


# ─── Debug (dev only) ────────────────────────────────────────────────────────
@app.get("/debug/config")
async def debug_config():
    """Shows masked config values — helps diagnose env var issues."""
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
