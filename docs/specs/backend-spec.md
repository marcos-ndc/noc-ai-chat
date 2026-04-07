# Spec: Backend API — NOC AI Agent
**Feature:** `feature/backend-api`
**Data:** 2026-04-07
**Status:** Aprovado

---

## Overview

Backend FastAPI que orquestra o agente de IA Claude, gerencia sessões de chat via WebSocket com streaming, autentica usuários via JWT e integra com MCP servers de cada ferramenta NOC (Zabbix, Datadog, Grafana, ThousandEyes).

---

## User Journeys

### J1 — Autenticação
1. Frontend POST `/auth/login` com email/senha
2. Backend valida credenciais
3. Retorna JWT (8h) + dados do usuário

### J2 — Sessão de chat via WebSocket
1. Frontend conecta em `ws://<host>/ws/chat?token=<jwt>`
2. Backend valida token, cria/retoma sessão Redis
3. Frontend envia `{ type: "user_message", content, sessionId }`
4. Orchestrator chama MCP tools emitindo `tool_start`/`tool_end`
5. Tokens chegam via `agent_token` em streaming
6. Resposta completa dispara `agent_done`

---

## Functional Requirements

- **FR-1:** POST `/auth/login` retorna JWT + User em caso de sucesso
- **FR-2:** Tokens inválidos/expirados retornam HTTP 401
- **FR-3:** WebSocket em `/ws/chat?token=` com autenticação JWT
- **FR-4:** Histórico de conversa por sessão no Redis (TTL 24h)
- **FR-5:** Streaming de tokens via WebSocket (`agent_token`)
- **FR-6:** Eventos `tool_start` e `tool_end` durante consultas MCP
- **FR-7:** System prompt especializado NOC em toda chamada ao Claude
- **FR-8:** System prompt adaptado ao perfil do usuário (N1/N2/engineer/manager)
- **FR-9:** Reconexão automática ao Redis em falha
- **FR-10:** `GET /health` retorna status dos serviços dependentes
- **FR-11:** Histórico limitado a 50 turnos (resumo automático)
- **FR-12:** Logs estruturados JSON de todas as interações

---

## Non-Functional Requirements

- **NFR-1:** Primeiro token < 2s após receber mensagem
- **NFR-2:** ≥ 20 conexões WebSocket simultâneas sem degradação
- **NFR-3:** API keys apenas via variáveis de ambiente
- **NFR-4:** Zero secrets nos logs
- **NFR-5:** Inicialização do container < 10s

---

## Out of Scope (v1)

- SSO/OAuth2
- Rate limiting
- Write operations via MCP
- Multi-tenancy
- Métricas Prometheus

---

## Dependencies

- Anthropic API (claude-sonnet-4-20250514)
- Redis 7+
- MCP Servers (zabbix, datadog, grafana, thousandeyes)
- Python 3.12+
