# Tasks: Testes de Integração
**Branch:** `feature/integration-tests`
**Data:** 2026-04-07

---

## Phase 0 — Setup

- [ ] **T201** [S] Instalar dependências de teste (pytest, httpx async, pytest-asyncio)
- [ ] **T202** [S] Criar conftest.py com fixtures globais (app TestClient, mock Redis)

## Phase 1 — Testes de API

- [ ] **T203** [P] Testes de integração: POST /auth/login (válido, inválido, campos faltando)
- [ ] **T204** [P] Testes de integração: GET /health (Redis ok, Redis down)
- [ ] **T205** [P] Testes de integração: WebSocket /ws/chat (auth, ping/pong, mensagem)

## Phase 2 — Testes MCP Servers

- [ ] **T206** [P] Teste health de cada MCP server (mock mode)
- [ ] **T207** [P] Teste de cada tool em modo mock (sem API real)
- [ ] **T208** [P] Teste de tratamento de erro (MCP server down)

## Phase 3 — Validação Docker

- [ ] **T209** [S] Validar docker-compose.yml sintaxe
- [ ] **T210** [S] Script de smoke test pós-deploy

## Phase 4 — CI/CD

- [ ] **T211** [S] GitHub Actions workflow: lint + testes a cada push
- [ ] **T212** [S] GitHub Actions workflow: build Docker images

## Phase 5 — Documentação

- [ ] **T213** [S] README atualizado com instruções de setup e execução
- [ ] **T214** [S] CONTRIBUTING.md com fluxo de desenvolvimento
