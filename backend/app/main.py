import structlog
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
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

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NOC AI Chat API",
    version="1.0.0",
    description="Backend do agente de IA especializado em operações NOC",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(health_router)


# ─── WebSocket ───────────────────────────────────────────────────────────────
@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await handle_chat_websocket(websocket)


# ─── Startup / Shutdown ──────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    log.info("noc_ai_chat.started", model=settings.claude_model)


@app.on_event("shutdown")
async def shutdown():
    log.info("noc_ai_chat.stopped")
