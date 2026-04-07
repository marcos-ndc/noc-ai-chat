# Spec: Testes de Integração — NOC AI Chat
**Feature:** `feature/integration-tests`
**Data:** 2026-04-07
**Status:** Aprovado

---

## Overview

Validação end-to-end do stack completo: frontend → backend → Claude API → MCP servers.
Cobre os fluxos críticos que garantem que o sistema funciona como um todo antes de ir para produção.

---

## Escopos de Teste

### 1. Testes de API (Backend)
- Autenticação: login válido, inválido, token expirado
- WebSocket: conexão, autenticação, envio/recebimento de mensagens
- Health endpoint: status dos serviços dependentes

### 2. Testes de MCP Servers
- Cada servidor responde em `/health`
- Tools retornam dados mock quando APIs não configuradas
- Tratamento de erro quando ferramenta indisponível

### 3. Teste de Smoke (Docker Compose)
- Stack sobe completo com `docker-compose up`
- Frontend acessível na porta 3000
- Backend acessível na porta 8000
- Health check verde em todos os containers

### 4. Teste de Fluxo Completo (E2E)
- Login → WebSocket → mensagem → resposta em streaming → agent_done

---

## Acceptance Criteria

- Todos os testes de API passam sem servidor real (mocks)
- `docker-compose config` valida sem erros
- Health endpoint retorna `status: ok` para Redis
- Fluxo WebSocket completo: login → connect → send → stream → done

---

## Out of Scope

- Testes com APIs reais das ferramentas NOC (requerem credenciais)
- Testes de carga / performance
- Testes de UI (Playwright/Cypress) — fase futura
