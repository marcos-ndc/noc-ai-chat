from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class UserProfile(str, Enum):
    N1 = "N1"
    N2 = "N2"
    engineer = "engineer"
    manager = "manager"

class MessageRole(str, Enum):
    user = "user"
    agent = "agent"

class WSEventType(str, Enum):
    user_message = "user_message"
    agent_token  = "agent_token"
    agent_done   = "agent_done"
    tool_start   = "tool_start"
    tool_end     = "tool_end"
    error        = "error"
    ping         = "ping"
    pong         = "pong"

class ToolName(str, Enum):
    zabbix       = "zabbix"
    datadog      = "datadog"
    grafana      = "grafana"
    thousandeyes = "thousandeyes"


# ─── Auth ────────────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: str
    name: str
    email: str
    profile: UserProfile
    avatarInitials: str

class AuthResponse(BaseModel):
    token: str
    user: UserOut

class TokenPayload(BaseModel):
    sub: str          # user id
    email: str
    profile: UserProfile
    exp: int


# ─── Chat ────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SessionData(BaseModel):
    session_id: str
    user_id: str
    user_profile: UserProfile
    messages: list[ChatMessage] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── WebSocket Events ────────────────────────────────────────────────────────

class WSInbound(BaseModel):
    type: WSEventType
    content: Optional[str] = None
    sessionId: Optional[str] = None
    voiceMode: bool = False  # True quando mensagem veio de entrada por voz

class WSOutbound(BaseModel):
    type: WSEventType
    messageId: Optional[str] = None
    content: Optional[str] = None
    tool: Optional[ToolName] = None
    error: Optional[str] = None

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)


# ─── Health ──────────────────────────────────────────────────────────────────

class ServiceStatus(BaseModel):
    name: str
    status: str   # "ok" | "degraded" | "down"
    latency_ms: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    services: list[ServiceStatus]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
