# Tasks: Backend API
**Branch:** `feature/backend-api`
**Data:** 2026-04-07

---

## Phase 0 — Setup

- [ ] **T101** [S] Configurar projeto Python: pyproject.toml, requirements, estrutura app/
- [ ] **T102** [S] Definir modelos Pydantic centrais (User, Message, WSEvent, AuthRequest)
- [ ] **T103** [S] Configurar settings via Pydantic BaseSettings

## Phase 1 — Testes (RED first)

- [ ] **T104** [P] Testes AuthService (login, JWT encode/decode, expiração)
- [ ] **T105** [P] Testes SessionManager (save, load, append, TTL)
- [ ] **T106** [P] Testes AgentOrchestrator (system prompt, histórico, streaming mock)
- [ ] **T107** [P] Testes health endpoint

## Phase 2 — Implementação Core

- [ ] **T108** [S] AuthService + POST /auth/login — T104 GREEN
- [ ] **T109** [S] SessionManager Redis — T105 GREEN
- [ ] **T110** [S] System prompt NOC por perfil de usuário
- [ ] **T111** [S] AgentOrchestrator Claude API + streaming — T106 GREEN
- [ ] **T112** [S] WebSocket handler /ws/chat com auth guard
- [ ] **T113** [S] GET /health com checks Redis + MCP

## Phase 3 — MCP Servers

- [ ] **T114** [S] MCP Zabbix (get_active_alerts, get_host_status, get_trigger_history)
- [ ] **T115** [S] MCP Datadog (get_active_monitors, get_metrics, get_incidents)
- [ ] **T116** [S] MCP Grafana (get_firing_alerts, get_alert_rules)
- [ ] **T117** [S] MCP ThousandEyes (get_active_alerts, get_test_results)

## Phase 4 — Docker e Validação

- [ ] **T118** [S] Dockerfile backend multi-stage
- [ ] **T119** [S] Dockerfiles MCP servers
- [ ] **T120** [S] Testes integração WebSocket end-to-end
- [ ] **T121** [S] Validação docker-compose up stack completo
