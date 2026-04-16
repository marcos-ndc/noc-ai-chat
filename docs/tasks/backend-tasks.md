# Tasks: Backend API
**Versão:** 2.0 | **Data:** 2026-04-09 | **Branch:** `main` (mergeado)

---

## Phase 0 — Setup ✅

- [x] **T101** Configurar projeto Python: requirements.txt, estrutura app/
- [x] **T102** Definir modelos Pydantic centrais (User, ChatMessage, WSEvent, ToolName, SessionData)
- [x] **T103** Configurar Settings via Pydantic BaseSettings (lê `.env` e `../.env`)

## Phase 1 — Testes ✅

- [x] **T104** Testes AuthService (login, JWT encode/decode, expiração, bcrypt)
- [x] **T105** Testes SessionManager (save, load, append, trim, TTL)
- [x] **T106** Testes AgentOrchestrator (system prompt, histórico, streaming mock)
- [x] **T107** Testes health endpoint

**Resultado:** 39 testes passando

## Phase 2 — Implementação Core ✅

- [x] **T108** AuthService + POST /auth/login (bcrypt direto, sem passlib)
- [x] **T109** SessionManager Redis — TTL 24h, max 50 turnos, role mapping correto
- [x] **T110** System prompt NOC por perfil + instruções de gráficos chart JSON
- [x] **T111** AgentOrchestrator — **AsyncAnthropic** + loop agêntico + streaming real
- [x] **T112** WebSocket handler /ws/chat com auth guard, ConnectionManager
- [x] **T113** GET /health com checks Redis + MCP servers
- [x] **T113b** GET /debug/config com chaves mascaradas para diagnóstico

## Phase 3 — MCP Servers ✅

- [x] **T114** MCP Zabbix — 8 tools com suporte multi-cliente (tag Organization)
- [x] **T115** MCP Datadog — 5 tools, health cacheado, debug/monitors
- [x] **T116** MCP Grafana — 2 tools
- [x] **T117** MCP ThousandEyes — 6 tools, API v7, endpoints corretos por tipo

## Phase 4 — Docker e Validação ✅

- [x] **T118** Dockerfile backend (multi-stage)
- [x] **T119** Dockerfiles MCP servers
- [x] **T120** docker-compose.yml + docker-compose.dev.yml com hot-reload
- [x] **T121** Validação stack completo funcionando

## Phase 5 — Bugfixes (Code Review) ✅

- [x] **T122** CR-2: Migrar para AsyncAnthropic (síncrono bloqueava event loop)
- [x] **T123** CR-3: Streaming real via `messages.stream()` (fake chunking removido)
- [x] **T124** CR-5: Role mapping `agent → assistant` corrigido
- [x] **T125** AL-2: `datetime.utcnow()` → `datetime.now(timezone.utc)`
- [x] **T126** AL-3: MCP URLs com porta correta (8001 interna, não 8002/8003/8004)
- [x] **T127** Fix: ANTHROPIC_API_KEY passada explicitamente no docker-compose
- [x] **T128** Fix: Startup warning + log mascarado da chave carregada
- [x] **T129** Fix: Suporte SSL proxy corporativo (`ANTHROPIC_SSL_VERIFY`, `httpx.AsyncClient`)
- [x] **T130** Fix: Log completo de tool calls (stop_reason, tool_calls, error_detail)
- [x] **T131** Fix: docker-compose environment com valores reais (não apenas comentários)

## Próximas Tasks (Backlog)

- [ ] **T132** Rate limiting por usuário (FastAPI middleware)
- [ ] **T133** SSO/AD corporativo → v2
- [ ] **T134** Write operations MCP (silenciar alertas, criar tickets) → v3
- [ ] **T135** Métricas Prometheus / OpenTelemetry
- [ ] **T136** Cobertura de testes para MCP servers (além de mock)
- [ ] **T137** Paginação avançada nos resultados das tools
