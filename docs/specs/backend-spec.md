# Spec: Backend API — NOC AI Agent
**Versão:** 2.0 | **Data:** 2026-04-09 | **Status:** Implementado ✅

---

## Overview

Backend FastAPI que orquestra o agente IA Claude via AsyncAnthropic, gerencia sessões de chat via WebSocket com streaming real token-a-token, autentica usuários via JWT e despacha tool calls para 4 MCP servers independentes (Zabbix, Datadog, Grafana, ThousandEyes).

---

## Arquitetura Implementada

```
backend/app/
├── main.py              # FastAPI app, CORS, lifespan, /debug/config
├── settings.py          # Pydantic BaseSettings, lê .env e ../.env
├── models.py            # Pydantic models (User, ChatMessage, WSEvent, ToolName...)
├── auth/
│   └── service.py       # JWT encode/decode, bcrypt, seed users
├── agent/
│   ├── orchestrator.py  # AgentOrchestrator (AsyncAnthropic + loop agêntico)
│   ├── session.py       # SessionManager (Redis, TTL 24h, 50 turnos)
│   ├── prompt.py        # System prompt NOC por perfil + instruções de gráficos
│   └── mcp_dispatcher.py # MCPDispatcher (roteamento de tool calls por prefixo)
├── routers/
│   ├── auth.py          # POST /auth/login
│   └── health.py        # GET /health
└── websocket/
    └── handler.py       # ConnectionManager, handle_chat_websocket
```

---

## User Journeys

### J1 — Autenticação
1. Frontend POST `/auth/login` com email/senha
2. Backend valida com bcrypt, retorna JWT (8h) + UserOut
3. JWT armazenado apenas em Zustand (memória)

### J2 — Sessão de chat com streaming real
1. Frontend conecta em `ws://<host>/ws/chat?token=<jwt>`
2. Backend valida JWT, cria/retoma sessão Redis (session_id do frontend)
3. Frontend envia `{ type: "user_message", content, sessionId }`
4. Orchestrator detecta necessidade de tools → emite `tool_start`
5. MCP dispatcher chama `http://mcp-<service>:8001/tools/<tool_name>`
6. Resultado retorna → emite `tool_end`
7. Loop agêntico: Claude processa resultados e decide se precisa de mais tools
8. Streaming real via `client.messages.stream()` → tokens chegam via `agent_token`
9. Resposta completa → `agent_done`, sessão salva no Redis

---

## Functional Requirements

| ID | Requisito | Status |
|----|-----------|--------|
| FR-1 | POST `/auth/login` retorna JWT + User | ✅ |
| FR-2 | Tokens inválidos/expirados retornam 401 | ✅ |
| FR-3 | WebSocket em `/ws/chat?token=` com auth JWT | ✅ |
| FR-4 | Histórico de conversa por sessão no Redis (TTL 24h) | ✅ |
| FR-5 | Streaming real de tokens via WebSocket (`agent_token`) | ✅ |
| FR-6 | Eventos `tool_start` e `tool_end` durante consultas MCP | ✅ |
| FR-7 | System prompt especializado NOC por perfil (N1/N2/engineer/manager) | ✅ |
| FR-8 | Loop agêntico: Claude pode chamar múltiplas tools antes de responder | ✅ |
| FR-9 | Reconexão automática ao Redis em falha | ✅ |
| FR-10 | `GET /health` com status dos serviços dependentes | ✅ |
| FR-11 | Histórico limitado a 50 turnos | ✅ |
| FR-12 | Logs estruturados JSON (structlog) | ✅ |
| FR-13 | `GET /debug/config` mostra chaves mascaradas para diagnóstico | ✅ |
| FR-14 | Role mapping correto: MessageRole.agent → "assistant" na API Claude | ✅ |
| FR-15 | Instruções de gráficos no system prompt (blocos `chart JSON`) | ✅ |

---

## MCP Tools Implementadas

### Zabbix (6 tools)
| Tool | Descrição |
|------|-----------|
| `zabbix_list_organizations` | Lista clientes pela tag Organization |
| `zabbix_get_organization_summary` | Resumo de saúde de um cliente |
| `zabbix_get_active_alerts` | Triggers ativos (filtro: org, severidade, grupo) |
| `zabbix_get_active_problems` | Problemas via problem.get (Zabbix 7.x) |
| `zabbix_get_host_status` | Status detalhado de um host |
| `zabbix_get_trigger_history` | Histórico de eventos de um host |
| `zabbix_get_item_latest` | Último valor de uma métrica (CPU, disco, etc.) |
| `zabbix_get_host_groups` | Lista grupos de hosts |

### Datadog (5 tools)
| Tool | Descrição |
|------|-----------|
| `datadog_get_active_monitors` | Monitors ativos por status/tags |
| `datadog_get_metrics` | Métricas de host/serviço |
| `datadog_get_logs` | Logs com filtro por query |
| `datadog_get_incidents` | Incidentes ativos |
| `datadog_get_hosts` | Hosts monitorados |

### Grafana (2 tools)
| Tool | Descrição |
|------|-----------|
| `grafana_get_firing_alerts` | Alertas disparando |
| `grafana_get_alert_rules` | Regras de alerta configuradas |

### ThousandEyes (6 tools)
| Tool | Descrição |
|------|-----------|
| `thousandeyes_list_tests` | Lista todos os testes |
| `thousandeyes_get_active_alerts` | Alertas ativos (HTTP, DNS, Network, BGP) |
| `thousandeyes_get_test_results` | Métricas de um teste (availability, latency, loss) |
| `thousandeyes_get_test_availability` | Disponibilidade de todos os testes |
| `thousandeyes_get_bgp_alerts` | Alertas BGP (hijacks, route leaks) |
| `thousandeyes_get_agents` | Agentes enterprise e cloud |

---

## Non-Functional Requirements

| ID | Requisito | Meta | Status |
|----|-----------|------|--------|
| NFR-1 | Primeiro token (TTFT) | < 3s | ✅ |
| NFR-2 | AsyncAnthropic — não bloqueia event loop | Obrigatório | ✅ |
| NFR-3 | API keys apenas via variáveis de ambiente | Obrigatório | ✅ |
| NFR-4 | Zero secrets nos logs (chaves mascaradas) | Obrigatório | ✅ |
| NFR-5 | Suporte a proxy SSL corporativo (`ANTHROPIC_SSL_VERIFY=false`) | Obrigatório | ✅ |
| NFR-6 | Health check com estado cacheado (não chama API externa a cada request) | Recomendado | ✅ Datadog |

---

## Bugs Corrigidos (Code Review 2026-04-08)

| ID | Bug | Correção |
|----|-----|----------|
| CR-2 | `Anthropic` síncrono bloqueava event loop | Migrado para `AsyncAnthropic` |
| CR-3 | Fake streaming (chunks simulados) | Streaming real via `messages.stream()` |
| CR-5 | Role mapping quebrado (`agent` nunca virava `assistant`) | `== MessageRole.user` |
| AL-2 | `datetime.utcnow()` depreciado | `datetime.now(timezone.utc)` |
| AL-3 | MCP URLs com portas erradas (8002/8003/8004) | Todos para porta interna 8001 |

---

## Out of Scope (v1)

- SSO/OAuth2 corporativo → v2
- Rate limiting por usuário
- Write operations via MCP (silenciar alertas, criar tickets) → v3
- Métricas Prometheus / OpenTelemetry
- Multi-tenancy (múltiplas instâncias isoladas)
