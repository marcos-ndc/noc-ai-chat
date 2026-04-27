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
    admin   = "admin"

class Specialist(str, Enum):
    generalista    = "generalista"
    apm            = "apm"
    infra          = "infra"
    conectividade  = "conectividade"
    observabilidade = "observabilidade"


SPECIALIST_LABELS: dict[str, str] = {
    "generalista":     "Generalista NOC",
    "apm":             "Especialista APM & Logs",
    "infra":           "Especialista Infraestrutura",
    "conectividade":   "Especialista Conectividade",
    "observabilidade": "Especialista Observabilidade",
}


class MessageRole(str, Enum):
    user = "user"
    agent = "agent"

class WSEventType(str, Enum):
    user_message = "user_message"
    agent_token  = "agent_token"
    agent_done   = "agent_done"
    tool_start   = "tool_start"
    tool_end          = "tool_end"
    specialist_change = "specialist_change"
    error             = "error"
    ping         = "ping"
    pong         = "pong"

class ToolName(str, Enum):
    zabbix          = "zabbix"
    datadog         = "datadog"
    grafana         = "grafana"
    thousandeyes    = "thousandeyes"
    catalyst        = "catalyst"


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
    active_specialist: str = Specialist.generalista   # specialist routing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── WebSocket Events ────────────────────────────────────────────────────────

class WSInbound(BaseModel):
    type: WSEventType
    content:    Optional[str] = None
    sessionId:  Optional[str] = None
    voiceMode:  bool = False
    specialist: Optional[str] = None  # manual specialist selection

class WSOutbound(BaseModel):
    type: WSEventType
    messageId:  Optional[str] = None
    content:    Optional[str] = None
    tool:       Optional[ToolName] = None
    error:      Optional[str] = None
    specialist: Optional[str] = None   # used in specialist_change events
    reason:     Optional[str] = None   # why the specialist was changed

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)



# --- AI Config -----------------------------------------------------------

class AIProvider(str, Enum):
    anthropic  = "anthropic"
    openrouter = "openrouter"

class AIConfig(BaseModel):
    provider:            AIProvider = AIProvider.anthropic
    model:               str        = "claude-sonnet-4-20250514"
    api_key:             str        = ""
    temperature:         float      = 1.0
    max_tokens:          int        = 4096
    openrouter_base_url: str        = "https://openrouter.ai/api/v1"
    site_url:            str        = ""
    site_name:           str        = "NOC AI Chat"

class AIConfigOut(BaseModel):
    """Public view of AI config - api_key is masked."""
    provider:            AIProvider
    model:               str
    api_key_set:         bool
    api_key_preview:     str
    temperature:         float
    max_tokens:          int
    openrouter_base_url: str
    site_name:           str

class ModelOption(BaseModel):
    id:          str
    name:        str
    provider:    AIProvider
    description: str
    context_k:   int


# ─── Health ──────────────────────────────────────────────────────────────────

class ServiceStatus(BaseModel):
    name: str
    status: str   # "ok" | "degraded" | "down"
    latency_ms: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    services: list[ServiceStatus]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
