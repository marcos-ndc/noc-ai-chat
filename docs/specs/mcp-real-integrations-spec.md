# Spec: Integração Real Zabbix 7.x + Datadog
**Feature:** `feature/mcp-real-integrations`
**Data:** 2026-04-07
**Status:** Aprovado

---

## Overview

Substituir os mocks dos MCP servers de Zabbix e Datadog por integrações reais,
mantendo o modo mock como fallback automático quando as variáveis de ambiente
não estiverem configuradas. Zabbix 7.x usa autenticação por API token (não mais
user/password direto). Datadog usa API Key + Application Key.

---

## Mudanças em relação ao mock

### Zabbix 7.x (breaking change vs 6.x)
- Autenticação: `user.login` retorna token de sessão → todas as chamadas incluem `auth`
- Zabbix 7.x adicionou suporte a **API tokens permanentes** (recomendado para integração)
- Novos campos nas respostas de triggers e eventos
- `trigger.get` substituído parcialmente por `problem.get` para problemas ativos

### Datadog
- Autenticação via headers `DD-API-KEY` e `DD-APPLICATION-KEY`
- Rate limits: 300 req/min para métricas, 1000 req/min para monitors
- Site configurável: `datadoghq.com`, `datadoghq.eu`, `us3.datadoghq.com`, etc.

---

## Functional Requirements

- **FR-1:** MCP Zabbix SHALL autenticar via API token (Zabbix 7.x) com fallback para user/password
- **FR-2:** MCP Zabbix SHALL renovar sessão automaticamente em caso de token expirado
- **FR-3:** MCP Zabbix SHALL retornar mock quando `ZABBIX_URL` não estiver configurado
- **FR-4:** MCP Datadog SHALL validar credenciais no startup e logar aviso se inválidas
- **FR-5:** MCP Datadog SHALL respeitar rate limits com retry automático (backoff)
- **FR-6:** MCP Datadog SHALL retornar mock quando `DATADOG_API_KEY` não estiver configurado
- **FR-7:** Ambos os MCP servers SHALL expor endpoint `GET /health` com latência real da API
- **FR-8:** Ambos SHALL ter timeout configurável via env var (padrão: 10s)
- **FR-9:** Erros de API SHALL ser retornados de forma estruturada para o agente interpretar
- **FR-10:** Logs SHALL incluir: tool chamada, latência, status — sem logar API keys

---

## Non-Functional Requirements

- **NFR-1:** Latência p95 das chamadas Zabbix < 3s em rede local
- **NFR-2:** Latência p95 das chamadas Datadog < 5s em cloud
- **NFR-3:** Cache de autenticação Zabbix — não re-autenticar em cada chamada
- **NFR-4:** Retry automático: máximo 2 tentativas com backoff de 1s em erro 5xx

---

## Out of Scope

- Write operations (criar/silenciar alertas)
- Webhooks / push notifications das ferramentas
- Grafana e ThousandEyes (permanecem mock nesta feature)
- Paginação avançada (máximo 100 resultados por chamada)
