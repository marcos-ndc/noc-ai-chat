# Tasks: NOC AI Chat
**Versão:** 3.1 | **Data:** 2026-04-21

---

## Backend ✅

- [x] FastAPI app, CORS, lifespan, settings Pydantic
- [x] Modelos: UserProfile, Specialist, AIConfig, WSEvent, SessionData
- [x] AuthService: bcrypt, JWT, 5 seed users incluindo admin
- [x] SessionManager: Redis, TTL 24h, 50 turnos, active_specialist
- [x] AgentOrchestrator: AsyncAnthropic + loop agêntico + streaming real
- [x] llm_client.py: AsyncAnthropic (Anthropic) | AsyncOpenAI (OpenRouter)
- [x] Conversão bidirecional Anthropic ↔ OpenAI para histórico
- [x] prompt.py: _LANGUAGE_PREMISE + 5 specialist prompts + _VOICE_ADDENDUM
- [x] ROUTE_TO detection: regex + session update + specialist_change WS event
- [x] AIConfigStore: Redis persistência + in-memory cache
- [x] routers/admin.py: catálogo 19 modelos, config runtime, test com diagnóstico
- [x] routers/tts.py: OpenAI TTS proxy, 6 vozes, tts-1-hd padrão
- [x] routers/stt.py: OpenAI Whisper proxy, language=pt, prompt NOC
- [x] python-multipart: dependência para UploadFile/Form
- [x] MCPDispatcher: roteamento por prefixo de tool name
- [x] mcp-zabbix: 8 tools, _enrich_triggers(), multi-cliente
- [x] Premissa pt-BR: _LANGUAGE_PREMISE no topo de todos os system prompts
- [x] python-multipart: dependência para UploadFile/Form (stt.py)
- [x] mcp-datadog: 5 tools, health cacheado
- [x] mcp-grafana: 2 tools
- [x] mcp-thousandeyes: 6 tools, API v7
- [x] Dockerfiles: multi-stage, CMD python -m uvicorn
- [x] SSL proxy: ANTHROPIC_SSL_VERIFY, OPENROUTER_SSL_VERIFY=false padrão
- [x] Erros sem HTML (strip de tags, diagnóstico por isinstance())

## Frontend ✅

- [x] React 18 + TypeScript strict + Vite + Tailwind
- [x] useAuth (Zustand), LoginPage, redirect guard, botões rápidos
- [x] useWebSocket: stable refs, backoff, reconexão
- [x] ChatPage: streaming, voiceMode, activeSpecialist, handsFree
- [x] ChatMessage/AgentContent: markdown + Recharts intercalados
- [x] NocCharts: 6 componentes + chartParser
- [x] StatusIndicator: tool em uso animado
- [x] SpecialistSelector: dropdown 5 especialistas
- [x] SpecialistToast: notificação de roteamento (4s)
- [x] useWhisperInput: MediaRecorder + POST /stt/transcribe
- [x] useVoiceInput: Web Speech API (standby/fallback)
- [x] useVoiceOutput: Audio() TTS premium + Web Speech fallback
- [x] VoiceOutputToggle: badge "AI" premium
- [x] stripForVoice(): remove markdown antes do TTS
- [x] useWakeWord: hands-free, wake/stop words pt-BR, isActive ref
- [x] VoiceModal: Canvas NDX, Web Audio API, ondas em tempo real
- [x] Header: voiceMode, handsFreeState, botão Admin
- [x] AdminPage: seletor modelo, TTS, status serviços
- [x] PWA: manifest + service worker

## Testes ✅ (105 passando)

- [x] test_auth_service.py
- [x] test_session_manager.py
- [x] test_api_auth.py
- [x] test_api_websocket.py (AsyncMock + settings patch)
- [x] test_mcp_servers.py (4 MCP servers em mock mode)
- [x] test_real_integrations.py (shapes corretos + env vars)

## Backlog

- [ ] Testes E2E com Playwright
- [ ] Rate limiting por usuário
- [ ] SSO/AD corporativo
- [ ] Write operations MCP (silenciar alertas, criar tickets)
- [ ] Deploy Azure Container Apps com CI/CD
- [ ] Notificações push para P1/P2
- [ ] Exportar conversa como PDF
- [ ] Métricas Prometheus / OpenTelemetry
