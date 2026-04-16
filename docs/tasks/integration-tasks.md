# Tasks: Integração e DevOps
**Versão:** 2.0 | **Data:** 2026-04-09 | **Branch:** `main` (mergeado)

---

## Phase 0 — Setup ✅

- [x] **T201** Dependências de teste: pytest, httpx async, pytest-asyncio, fakeredis
- [x] **T202** `conftest.py` com fixtures globais (app TestClient, mock Redis)

## Phase 1 — Testes de API ✅

- [x] **T203** POST /auth/login (válido, inválido, campos faltando)
- [x] **T204** GET /health (Redis ok, services)
- [x] **T205** WebSocket /ws/chat (auth, ping/pong, mensagem)

## Phase 2 — Testes MCP Servers ✅

- [x] **T206** Health de cada MCP server em modo mock
- [x] **T207** Cada tool em modo mock (sem API real)
- [x] **T208** Tratamento de erro (MCP server down → `{"error": "..."}`)

## Phase 3 — Docker ✅

- [x] **T209** docker-compose.yml validado (YAML + environment válidos)
- [x] **T210** docker-compose.dev.yml com hot-reload para backend e MCP servers
- [x] **T211** Scripts: `setup-dev.sh`, `check-ports.sh`, `smoke_test.py`
- [x] **T212** Makefile com targets: `dev`, `prod`, `test`, `lint`, `smoke`

## Phase 4 — CI/CD ✅

- [x] **T213** GitHub Actions: `ci.yml` (backend tests + frontend build + MCP lint)
- [x] **T214** GitHub Actions: `docker-build.yml` (push para GHCR em main/tags)

## Phase 5 — Proxy Corporativo ✅

- [x] **T215** Documentação `CORPORATE-PROXY.md`
- [x] **T216** `ANTHROPIC_SSL_VERIFY=false` no backend (httpx.AsyncClient custom)
- [x] **T217** `SSL_VERIFY=false` default em todos os MCP servers
- [x] **T218** Diagnóstico detalhado no startup de cada MCP server

## Phase 6 — Documentação ✅

- [x] **T219** README.md com instruções completas de setup
- [x] **T220** CONTRIBUTING.md com fluxo de desenvolvimento
- [x] **T221** CODE-REVIEW-2026-04-08.md com todos os bugs encontrados e corrigidos
- [x] **T222** SUCCESS_METRICS.json com 33 métricas em 8 categorias
- [x] **T223** Specs e tasks atualizados para refletir estado real (esta task)

## Próximas Tasks (Backlog)

- [ ] **T224** Testes E2E com Playwright (login → chat → ferramenta → resposta)
- [ ] **T225** Load testing: 20+ conexões WS simultâneas
- [ ] **T226** Monitoramento do próprio stack com Zabbix (dogfooding)
- [ ] **T227** Deploy em Azure Container Apps com CI/CD automático
- [ ] **T228** Rotação automática de JWT_SECRET sem downtime
- [ ] **T229** Dashboard de métricas de uso (sessions, messages, tool calls por dia)
