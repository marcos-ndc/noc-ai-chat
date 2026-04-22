# Spec: Backend API
**Versão:** 3.0 | **Data:** 2026-04-21 | **Status:** Implementado ✅

---

## Functional Requirements

| ID | Requisito | Status |
|----|-----------|--------|
| FR-1 | POST `/auth/login` retorna JWT + UserOut | ✅ |
| FR-2 | WebSocket `/ws/chat?token=` com auth JWT | ✅ |
| FR-3 | Streaming real token a token (AsyncAnthropic/AsyncOpenAI) | ✅ |
| FR-4 | Histórico de sessão no Redis (TTL 24h, 50 turnos) | ✅ |
| FR-5 | Loop agêntico: múltiplas tool calls antes de responder | ✅ |
| FR-6 | 5 especialistas com system prompts específicos | ✅ |
| FR-7 | Detecção automática de `<ROUTE_TO>` → `specialist_change` WS | ✅ |
| FR-8 | `session.active_specialist` persiste entre mensagens | ✅ |
| FR-9 | Seleção manual de especialista via `WSInbound.specialist` | ✅ |
| FR-10 | Premissa de idioma pt-BR em todos os prompts | ✅ |
| FR-11 | System prompt adaptado por perfil (N1/N2/engineer/manager/admin) | ✅ |
| FR-12 | Modo voz: `_VOICE_ADDENDUM` no TOPO do prompt (prioridade máxima) | ✅ |
| FR-13 | AIConfigStore: provedor/modelo/key configuráveis em runtime | ✅ |
| FR-14 | OpenRouter via `AsyncOpenAI` (Anthropic SDK rejeita o host) | ✅ |
| FR-15 | Conversão de mensagens Anthropic ↔ OpenAI para histórico | ✅ |
| FR-16 | POST `/tts/speak` → OpenAI TTS → MP3 | ✅ |
| FR-17 | GET `/tts/status` → vozes disponíveis | ✅ |
| FR-18 | POST `/stt/transcribe` → OpenAI Whisper → texto | ✅ |
| FR-19 | GET `/stt/status` → disponibilidade do Whisper | ✅ |
| FR-20 | `/admin/*` endpoints com guard de perfil admin | ✅ |
| FR-21 | GET `/admin/models` → catálogo de 19 modelos | ✅ |
| FR-22 | PUT `/admin/ai-config` → atualiza em runtime sem reiniciar | ✅ |
| FR-23 | POST `/admin/ai-config/test` → diagnóstico por tipo de erro | ✅ |
| FR-24 | Erros sem HTML (strip de tags antes de exibir) | ✅ |
| FR-25 | SSL proxy corporativo via `ANTHROPIC_SSL_VERIFY=false` | ✅ |
| FR-26 | OpenRouter SSL desabilitado por padrão | ✅ |

---

## Rotas

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/auth/login` | — | Login, retorna JWT |
| WS | `/ws/chat?token=` | JWT | Chat com streaming |
| POST | `/tts/speak` | — | OpenAI TTS → MP3 |
| GET | `/tts/status` | — | Disponibilidade TTS |
| POST | `/stt/transcribe` | — | Whisper STT → texto |
| GET | `/stt/status` | — | Disponibilidade STT |
| GET | `/admin/models` | admin | Catálogo de modelos |
| GET | `/admin/ai-config` | admin | Config atual mascarada |
| PUT | `/admin/ai-config` | admin | Atualiza config runtime |
| POST | `/admin/ai-config/test` | admin | Testa conexão |
| GET | `/admin/status` | admin | Status IA + Redis + MCPs |
| GET | `/health` | — | Health check geral |
| GET | `/debug/config` | — | Variáveis mascaradas |

---

## MCP Tools (21 total)

### Zabbix (8)
`zabbix_list_organizations`, `zabbix_get_organization_summary`, `zabbix_get_active_alerts`, `zabbix_get_active_problems`, `zabbix_get_host_status`, `zabbix_get_trigger_history`, `zabbix_get_item_latest`, `zabbix_get_host_groups`

### Datadog (5)
`datadog_get_active_monitors`, `datadog_get_metrics`, `datadog_get_logs`, `datadog_get_incidents`, `datadog_get_hosts`

### Grafana (2)
`grafana_get_firing_alerts`, `grafana_get_alert_rules`

### ThousandEyes (6)
`thousandeyes_list_tests`, `thousandeyes_get_active_alerts`, `thousandeyes_get_test_results`, `thousandeyes_get_test_availability`, `thousandeyes_get_bgp_alerts`, `thousandeyes_get_agents`

---

## Modelos no Catálogo (19)

**Anthropic (4):** claude-opus-4-5, claude-sonnet-4-5, claude-sonnet-4-20250514, claude-haiku-4-5-20251001

**OpenRouter (15):** anthropic/claude-opus-4-5, anthropic/claude-sonnet-4-5, anthropic/claude-haiku-4-5, openai/gpt-4o, openai/gpt-4o-mini, openai/gpt-oss-120b, google/gemini-2.5-flash-lite, google/gemini-2.0-flash-001, meta-llama/llama-3.3-70b-instruct, meta-llama/llama-3.1-8b-instruct, mistralai/mistral-large-2512, mistralai/mistral-small-3.2-24b-instruct-2506, deepseek/deepseek-r1, nvidia/nemotron-3-super-120b-a12b, qwen/qwen3-235b-a22b

**Nota:** IDs OpenRouter nunca usam sufixo `:free`. Não usar `Anthropic SDK` com base_url do OpenRouter.

---

## Bugs Corrigidos Notáveis

| Fix | Problema |
|-----|----------|
| AsyncAnthropic | Síncrono bloqueava event loop |
| llm_client.py | Anthropic SDK tem allowlist de hosts — OpenRouter usa AsyncOpenAI |
| _messages_to_openai | Retornava lista em vez de dict para tool_results (HTTP 400) |
| voiceMode state | setState async — send() usava valor antigo (sempre false) |
| ROUTE_TO cleanup | Tag XML removida do histórico armazenado |
| _enrich_triggers | Função chamada mas nunca definida no mcp-zabbix |
| python-multipart | Ausente — FastAPI não processa UploadFile sem ele |

---

## Segurança (v3.2)

### Row Level Security
```python
# websocket/handler.py — get_or_create_session()
if session.user_id != user.id:
    raise PermissionError("Session belongs to a different user")
```

### Auth Dependency
```python
# app/auth/dependencies.py
from app.auth.dependencies import get_current_user, require_admin

# Em qualquer router:
async def meu_endpoint(_: UserOut = Depends(get_current_user)): ...
async def admin_endpoint(_: UserOut = Depends(require_admin)): ...
```

### Security Headers Middleware
Injetado em `main.py` via `SecurityHeadersMiddleware(BaseHTTPMiddleware)`.
Em produção (`CORS_ALLOW_ALL=false`), adiciona também `Content-Security-Policy` e `HSTS`.

### CORS Produção
```env
CORS_ALLOW_ALL=false
CORS_ORIGINS=["https://noc.suaempresa.com"]
APP_DOMAIN=noc.suaempresa.com
```

### TTS/STT — Leitura de env a cada request
```python
def _cfg():
    return {
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "el_key":     os.getenv("ELEVENLABS_API_KEY", ""),
        ...
    }
```
Padrão obrigatório: nunca ler env vars no nível de módulo para TTS/STT.
