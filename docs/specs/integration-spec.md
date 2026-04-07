# Spec: Integration Tests & Stack Validation
**Feature:** `feature/integration-tests`
**Data:** 2026-04-07
**Status:** Aprovado

---

## Overview

Testes de integração que validam o stack completo: frontend conecta ao backend via WebSocket, backend autentica e processa mensagens, Agent Orchestrator chama MCP tools, respostas chegam em streaming ao frontend. Inclui também um mock server para desenvolvimento sem Anthropic API key.

---

## Functional Requirements

- **FR-1:** Teste de integração valida fluxo completo: login → WebSocket → mensagem → streaming → resposta
- **FR-2:** Mock server substitui Anthropic API em ambiente de teste/dev
- **FR-3:** Script de smoke test valida que `docker-compose up` sobe todos os serviços
- **FR-4:** CI/CD pipeline (GitHub Actions) roda testes automaticamente em cada PR
- **FR-5:** README atualizado com instruções completas de setup e execução

---

## Out of Scope

- Testes E2E com browser (Playwright/Cypress) — fase futura
- Load testing — fase futura
