# NOC AI Chat — Project Constitution
**Versão:** 3.2 | **Data:** 2026-04-22 | **Anterior:** 3.1 (2026-04-21)

Documento não-negociável que governa todo o desenvolvimento do projeto.
Specs, planos e tasks não podem contradizer esta constituição sem revisão explícita.

---

## 1. Visão do Produto

Assistente de IA conversacional para NOC (Network Operations Center) com:
- **Multimodal**: texto, voz de entrada (Whisper), voz de saída (OpenAI TTS / ElevenLabs)
- **Hands-free**: wake word "Olá NOC", cumprimento ao ativar, despedida ao encerrar
- **Multi-especialista**: 5 agentes com domínios distintos + roteamento automático + handoff de contexto
- **Multi-provedor**: Anthropic direto ou qualquer modelo via OpenRouter
- **Multi-ferramenta**: Zabbix, Datadog, Grafana, ThousandEyes
- **Idioma**: sempre Português Brasileiro (pt-BR) — premissa inegociável
- **Segurança**: RLS por sessão, CORS restrito em produção, security headers em todas as respostas

---

## 2. Arquitetura

```
Browser (React 18 PWA)
  ├── Chat (texto + Markdown + Recharts)
  ├── Voz entrada: OpenAI Whisper → POST /stt/transcribe [JWT obrigatório]
  ├── Voz saída: ElevenLabs / OpenAI TTS → POST /tts/speak [JWT obrigatório]
  │     └── Fallback automático: ElevenLabs → OpenAI → Web Speech API
  ├── Wake word: Web Speech API (standby) + Whisper (listening)
  ├── Modal NDX: Canvas + Web Audio API (ondas em tempo real)
  └── Cumprimentos: TTS fala ao ativar/desativar modo voz
        ↓ WebSocket streaming (JWT via query param)
Backend (FastAPI + AsyncAnthropic/AsyncOpenAI)
  ├── SecurityHeadersMiddleware (X-Frame-Options, CSP, HSTS, etc.)
  ├── CORSMiddleware (restrito em produção)
  ├── AgentOrchestrator (loop agêntico, streaming real)
  ├── AIConfigStore (provedor/modelo/key em runtime via Redis)
  ├── SpecialistRouter (5 especialistas, ROUTE_TO + handoff de contexto)
  ├── auth/dependencies.py (get_current_user, require_admin — Depends reutilizável)
  └── MCPDispatcher → MCP Servers
        ├── mcp-zabbix      (8 tools, multi-cliente, tag Organization)
        ├── mcp-datadog     (5 tools, health cacheado)
        ├── mcp-grafana     (2 tools)
        └── mcp-thousandeyes (6 tools, API v7)
              ↕ Redis (sessões com RLS user_id, histórico 50 turnos, TTL 24h)
```

---

## 3. Stack

### Frontend

| Categoria | Tecnologia |
|-----------|-----------|
| Framework | React 18 + TypeScript 5 strict |
| Build | Vite 5 |
| Estilo | Tailwind CSS 3 |
| Estado | Zustand 4 |
| Gráficos | Recharts 2 + react-is |
| Áudio entrada | Web Speech API (standby) + OpenAI Whisper via `/stt/transcribe` |
| Áudio saída | ElevenLabs TTS (prioridade) + OpenAI TTS (fallback) via `/tts/speak` |
| Animação voz | Canvas 2D + Web Audio API (AnalyserNode) |
| PWA | vite-plugin-pwa |

**Proibido:** Redux, jQuery, Bootstrap, MUI, Ant Design.

### Backend

| Categoria | Tecnologia |
|-----------|-----------|
| Framework | FastAPI 0.115+ |
| IA Anthropic | anthropic.AsyncAnthropic |
| IA OpenRouter | openai.AsyncOpenAI (OpenAI-compatible) |
| Cache | Redis 7 (redis.asyncio) |
| Auth | python-jose + bcrypt |
| Upload | python-multipart (Form/File endpoints) |
| HTTP | httpx.AsyncClient |
| Logs | structlog JSON |

**Regra crítica:** sempre `AsyncAnthropic` — nunca `Anthropic` síncrono.
**Regra crítica:** OpenRouter usa `AsyncOpenAI` — Anthropic SDK rejeita o host.
**Regra crítica:** env vars de TTS/STT lidas via `_cfg()` a cada request — nunca no import.

---

## 4. Especialistas NOC

| ID | Nome | Ferramentas | Gatilho automático |
|----|------|-------------|-------------------|
| `generalista` | Generalista NOC | Todas | Entrada padrão, triagem |
| `apm` | APM & Logs | Datadog + Grafana | Erros HTTP, latência, traces |
| `infra` | Infraestrutura | Zabbix + Datadog | CPU, memória, disco, host down |
| `conectividade` | Conectividade | ThousandEyes | Latência de rede, BGP, DNS |
| `observabilidade` | Observabilidade | Grafana + Datadog | Dashboards, SLOs, correlação |

### Roteamento automático
O Generalista emite `<ROUTE_TO specialist="X" reason="Y"/>`. O backend:
1. Detecta a tag via regex no `full_response`
2. Strip da tag na mensagem armazenada/exibida
3. Gera handoff de contexto com histórico dos últimos 10 turnos
4. Injeta o handoff como mensagem do usuário para o novo especialista
5. Atualiza `session.active_specialist`
6. Emite evento `specialist_change` via WebSocket
7. Frontend exibe `SpecialistToast` por 4s

---

## 5. Modo Voz

### STT (entrada)
- **Premium (Whisper)**: MediaRecorder → `POST /stt/transcribe` (JWT obrigatório)
  - `echoCancellation + noiseSuppression + autoGainControl` no microfone
  - Detecção de silêncio via Web Audio API AnalyserNode (1.5s → auto-stop)
  - Prompt NOC: termos técnicos para melhor reconhecimento
  - Timeout de segurança: 10s máximo por gravação
- **Fallback**: Web Speech API do Chrome

### TTS (saída)
- **ElevenLabs** (prioridade quando disponível): vozes nativas pt-BR
  - Modelo: `eleven_flash_v2_5` (~75ms latência)
  - Fallback automático para OpenAI se ElevenLabs indisponível (proxy, rede)
- **OpenAI TTS**: voz `nova` recomendada para pt-BR, modelo `tts-1-hd`
- **Fallback**: Web Speech API (SpeechSynthesisUtterance)
- Todos os endpoints TTS/STT exigem JWT válido (`Depends(get_current_user)`)
- Env vars lidas a cada request via `_cfg()` — mudanças no `.env` sem rebuild

### Hands-free
- **Ativar**: botão "Olá NOC" → TTS fala cumprimento aleatório → mic inicia
- **Standby**: Web Speech API contínua ouvindo wake words em background
- **Wake words**: "olá noc", "nokia", "nok" e variações pt-BR
- **Listening**: Whisper (se disponível) ou Web Speech API
- **Stop words**: "noc obrigado", "tchau noc", "pare noc" → TTS despedida → encerra
- **Loop automático**: TTS termina → 800ms → reinicia escuta
- **Modal NDX**: overlay Canvas com 6 anéis orbitais animados pelo microfone
- **Cumprimentos aleatórios**: 4 variações ao ativar, 4 ao desativar

---

## 6. Segurança

### Row Level Security (RLS)
- `SessionData.user_id` gravado no Redis no momento da criação
- `get_or_create_session()` verifica `session.user_id == user.id` em toda reconexão
- Acesso negado → `PermissionError` → log `rls.session_access_denied` + WSEventType.error

### CORS
- **Dev** (`CORS_ALLOW_ALL=true`): aceita qualquer origem
- **Prod** (`CORS_ALLOW_ALL=false`): apenas origens em `CORS_ORIGINS`
- Métodos permitidos: `GET, POST, PUT, DELETE, OPTIONS`
- Headers permitidos: `Authorization, Content-Type, Accept, X-Requested-With`

### Security Headers (todas as respostas)
| Header | Valor |
|--------|-------|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `microphone=(self), camera=(), geolocation=()...` |
| `Content-Security-Policy` | apenas em produção |
| `Strict-Transport-Security` | apenas em produção (HTTPS) |

### Auth Dependency
```python
from app.auth.dependencies import get_current_user, require_admin
# Uso:
async def endpoint(_: UserOut = Depends(get_current_user)): ...
async def admin_endpoint(_: UserOut = Depends(require_admin)): ...
```

### Debug endpoints
- `/debug/config` retorna 404 em produção (`CORS_ALLOW_ALL=false`)

---

## 7. Premissa de Idioma

**Inegociável:** o agente SEMPRE responde em Português Brasileiro.
A `_LANGUAGE_PREMISE` é inserida no topo de todos os system prompts,
antes de qualquer instrução específica de especialista ou perfil.

---

## 8. Painel de Administração

Rota `/admin`, acesso restrito ao perfil `admin`.

| Seção | Funcionalidade |
|-------|---------------|
| Modelo de IA | Seletor de provedor (Anthropic/OpenRouter) + modelo + API key |
| Testar conexão | POST `/admin/ai-config/test` com diagnóstico por tipo de erro |
| Status | IA, Redis, 4 MCP servers |
| Voz TTS | Provedor (ElevenLabs/OpenAI) + voz + modelo + velocidade |

**Catálogo:** 19 modelos — 4 Anthropic + 15 OpenRouter.
**Importante:** OpenRouter usa `AsyncOpenAI`, não `AsyncAnthropic`. IDs sem sufixo `:free`.

---

## 9. Variáveis de Ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `ANTHROPIC_API_KEY` | ✅ | Sem ela o agente não responde |
| `JWT_SECRET` | ✅ | `openssl rand -hex 32` |
| `OPENAI_API_KEY` | Recomendado | TTS `nova/onyx` + Whisper STT |
| `TTS_VOICE` | Opcional | Padrão: `nova` (melhor pt-BR) |
| `TTS_MODEL` | Opcional | Padrão: `tts-1-hd` |
| `TTS_SPEED` | Opcional | Padrão: `0.92` |
| `ELEVENLABS_API_KEY` | Opcional | TTS nativo pt-BR (prioridade sobre OpenAI) |
| `ELEVENLABS_MODEL` | Opcional | Padrão: `eleven_flash_v2_5` |
| `ELEVENLABS_VOICE_ID` | Opcional | ID da voz padrão na conta ElevenLabs |
| `WHISPER_MODEL` | Opcional | Padrão: `whisper-1` |
| `WHISPER_LANG` | Opcional | Padrão: `pt` |
| `CORS_ALLOW_ALL` | Opcional | `true` dev / `false` prod |
| `CORS_ORIGINS` | Prod | `["https://noc.suaempresa.com"]` |
| `APP_DOMAIN` | Prod | `noc.suaempresa.com` |
| `ANTHROPIC_SSL_VERIFY` | Opcional | `false` para proxy corporativo |
| `ZABBIX_URL` | Opcional | Mock se ausente |
| `DATADOG_API_KEY` | Opcional | Mock se ausente |
| `THOUSANDEYES_TOKEN` | Opcional | Mock se ausente |
| `GRAFANA_URL` | Opcional | Mock se ausente |

---

## 10. Usuários Seed

| Email | Senha | Perfil |
|-------|-------|--------|
| `admin@noc.local` | `admin123` | N2 |
| `n1@noc.local` | `noc2024` | N1 |
| `eng@noc.local` | `eng2024` | Engineer |
| `gestor@noc.local` | `mgr2024` | Manager |
| `admin-sys@noc.local` | `admin-noc-2024` | **Admin** |

---

## 11. Git & Qualidade

- Branches: `feature/`, `fix/`, `docs/`, `chore/`
- Commits: Conventional Commits
- TypeScript: strict, zero `any`, `tsc --noEmit` = 0 erros antes de merge
- Python: `py_compile` em todos os arquivos antes de commit
- Testes: `make test` deve passar — baseline: **167 testes**
