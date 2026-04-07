# NOC AI Agent Chat — Design Spec
**Data:** 2026-04-07  
**Status:** Aprovado  
**Versão:** 1.0

---

## 1. Visão Geral

Aplicação web responsiva (PWA) de chat com agente de IA especializado em operações de NOC. O agente possui conhecimento profundo em ferramentas de monitoramento (Zabbix, Datadog, Grafana, ThousandEyes) e em identificação e análise de incidentes. Usuários interagem via texto ou voz; o agente responde em tempo real consultando as ferramentas via MCP Tools.

### Objetivos
- Centralizar o acesso inteligente às ferramentas NOC em uma única interface conversacional
- Reduzir o tempo de identificação e diagnóstico de incidentes
- Adaptar a linguagem e profundidade das respostas ao perfil do usuário (N1, N2, Engenheiro, Gestor)
- Suportar interação por voz bidirecional (fala → texto → fala)

### Fora do escopo (v1)
- Automação de ações nas ferramentas (ex: silenciar alertas, criar tickets) — fase futura
- SSO/AD corporativo — previsto para v2
- App mobile nativo — PWA cobre mobile na v1

---

## 2. Usuários e Perfis

| Perfil | Necessidade principal |
|--------|-----------------------|
| Analista N1/N2 | Identificar e triagar incidentes ativos rapidamente |
| Engenheiro de Infraestrutura | Análise técnica profunda, correlação de eventos |
| Gestor/Líder Técnico | Visão executiva, status de ambientes, SLA |

O agente detecta o perfil via configuração no cadastro do usuário e adapta automaticamente a linguagem e o nível de detalhe das respostas.

---

## 3. Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                  FRONTEND (React PWA)                    │
│  Chat UI  │  Voice Input (STT)  │  Voice Output (TTS)   │
└───────────────────────┬─────────────────────────────────┘
                        │ WebSocket (streaming)
┌───────────────────────▼─────────────────────────────────┐
│                  BACKEND (FastAPI)                       │
│         Agent Orchestrator (Claude API)                  │
│   MCP Zabbix │ MCP Datadog │ MCP Grafana │ MCP ThousEyes│
└──────┬───────────┬──────────────┬──────────────┬────────┘
       │           │              │              │
  Zabbix API  Datadog API   Grafana API    ThousandEyes API
```

### Princípios arquiteturais
- **Backend-only para secrets:** nenhuma API key é exposta ao frontend
- **MCP por ferramenta:** cada integração é um MCP server independente, facilitando adição de novas ferramentas sem alterar o core
- **Streaming via WebSocket:** respostas palavra por palavra para UX fluida
- **Stateless com Redis:** sessões e histórico de conversa em Redis, backend pode escalar horizontalmente
- **Docker-first:** toda a stack roda em containers, portável para qualquer cloud

---

## 4. Componentes

### 4.1 Frontend (React + TypeScript + Tailwind CSS)

**Chat Interface**
- Histórico de conversa com renderização de Markdown
- Code blocks para configs, queries e comandos
- Indicador em tempo real da ferramenta sendo consultada ("🔍 Consultando Zabbix...")
- Suporte a anexos de screenshot (para análise pelo agente)

**Voice Input (STT)**
- Modo padrão: Web Speech API (nativo no browser, zero custo)
- Modo avançado: OpenAI Whisper API (mais preciso para termos técnicos)
- Botão de microfone com indicador visual de gravação

**Voice Output (TTS)**
- Modo padrão: Web Speech API (nativo)
- Modo avançado: OpenAI TTS (voz mais natural)
- Toggle para ativar/desativar resposta em áudio

**PWA**
- Instalável em desktop e mobile
- Notificações push para alertas críticos (fase futura)

### 4.2 Backend (Python + FastAPI)

**WebSocket Handler**
- Gerencia conexões persistentes por usuário
- Faz streaming das respostas do agente token a token
- Reconecta automaticamente em caso de queda

**Agent Orchestrator**
- Inicializa o Claude claude-sonnet-4-20250514 com system prompt especializado NOC
- Mantém o histórico da conversa na sessão (até 50 turnos, depois resumo automático)
- Decide quais MCP tools chamar com base na pergunta do usuário
- Adapta o tom e profundidade com base no perfil do usuário logado

**System Prompt do Agente**
O system prompt embute conhecimento sobre:
- Taxonomia de incidentes: P1 (crítico/indisponibilidade), P2 (degradação severa), P3 (degradação leve), P4 (informativo)
- Correlação de eventos entre múltiplas ferramentas
- Runbooks básicos de diagnóstico (CPU, memória, rede, disco, aplicação)
- Terminologia NOC: MTTR, MTTD, SLA, janela de manutenção, RCA
- Orientação proativa: ao detectar padrão de incidente, sugere próximos passos

**Auth Service**
- JWT com expiração de 8h (turno NOC)
- Refresh token automático
- Cadastro de usuário com perfil (N1/N2/Engenheiro/Gestor)
- Preparado para OAuth2/SSO na v2 (interface já abstraída)

**Session Manager (Redis)**
- Histórico de conversa por sessão
- TTL de 24h
- Permite retomar conversa após reconexão

### 4.3 MCP Servers

Cada MCP server é um container Python independente que expõe tools ao agente.

#### MCP Zabbix
```
Tools:
- get_active_alerts(severity, host, group, limit)
- get_host_status(hostname)
- get_trigger_history(host, hours, severity)
- get_recent_events(limit, severity)
- get_host_groups()
```

#### MCP Datadog
```
Tools:
- get_active_monitors(status, tags, priority)
- get_metrics(metric_name, host, from_time, to_time)
- get_recent_logs(service, level, limit)
- get_incidents(status, severity)
- get_dashboards_list()
```

#### MCP Grafana
```
Tools:
- get_alert_rules(state, folder)
- get_firing_alerts()
- get_dashboard_panels(dashboard_uid)
- get_datasources()
```

#### MCP ThousandEyes
```
Tools:
- get_test_results(test_id, window)
- get_active_alerts(type)
- get_agent_status()
- get_bgp_alerts()
```

---

## 5. Configuração das APIs (Passo a Passo)

### 5.1 Zabbix API
1. Acesse o Zabbix frontend → **Administration > Users**
2. Crie um usuário dedicado `noc-agent` com papel **Super Admin** (ou Read-Only se preferir menos permissões)
3. Anote o username e password
4. A URL da API é: `http(s)://<seu-zabbix>/api_jsonrpc.php`
5. Configure no `.env`: `ZABBIX_URL`, `ZABBIX_USER`, `ZABBIX_PASSWORD`
6. Teste: `curl -X POST <url> -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"user.login","params":{"username":"noc-agent","password":"<senha>"},"id":1}'`

### 5.2 Datadog API
1. Acesse **Organization Settings > API Keys** no Datadog
2. Clique em **New Key** → nomeie como `noc-agent`
3. Acesse **Organization Settings > Application Keys**
4. Clique em **New Key** → nomeie como `noc-agent-app`
5. Configure no `.env`: `DATADOG_API_KEY`, `DATADOG_APP_KEY`, `DATADOG_SITE` (ex: `datadoghq.com`)

### 5.3 Grafana API
1. Acesse o Grafana → **Administration > Service Accounts**
2. Clique em **Add service account** → nomeie como `noc-agent`, papel **Viewer**
3. Clique no service account criado → **Add service account token**
4. Copie o token gerado (aparece só uma vez)
5. Configure no `.env`: `GRAFANA_URL`, `GRAFANA_TOKEN`

### 5.4 ThousandEyes API
1. Acesse **Account Settings > Users and Roles** no ThousandEyes
2. Vá em **Security & Authentication > User API Tokens**
3. Gere um novo token OAuth Bearer
4. Configure no `.env`: `THOUSANDEYES_TOKEN`

---

## 6. Estrutura de Arquivos do Projeto

```
noc-ai-chat/
├── docker-compose.yml
├── .env.example
├── frontend/
│   ├── Dockerfile
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat/
│   │   │   ├── VoiceInput/
│   │   │   ├── VoiceOutput/
│   │   │   └── StatusIndicator/
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useVoiceInput.ts
│   │   │   └── useVoiceOutput.ts
│   │   ├── pages/
│   │   │   ├── Chat.tsx
│   │   │   └── Login.tsx
│   │   └── App.tsx
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── system_prompt.py
│   │   └── session_manager.py
│   ├── auth/
│   │   ├── jwt_handler.py
│   │   └── models.py
│   └── websocket/
│       └── handler.py
├── mcp-servers/
│   ├── zabbix/
│   │   ├── Dockerfile
│   │   └── server.py
│   ├── datadog/
│   │   ├── Dockerfile
│   │   └── server.py
│   ├── grafana/
│   │   ├── Dockerfile
│   │   └── server.py
│   └── thousandeyes/
│       ├── Dockerfile
│       └── server.py
└── docs/
    └── specs/
        └── 2026-04-07-noc-ai-agent-chat-design.md
```

---

## 7. Docker Compose

```yaml
version: '3.9'
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - VITE_BACKEND_URL=http://backend:8000

  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis, mcp-zabbix, mcp-datadog, mcp-grafana, mcp-thousandeyes]

  mcp-zabbix:
    build: ./mcp-servers/zabbix
    env_file: .env

  mcp-datadog:
    build: ./mcp-servers/datadog
    env_file: .env

  mcp-grafana:
    build: ./mcp-servers/grafana
    env_file: .env

  mcp-thousandeyes:
    build: ./mcp-servers/thousandeyes
    env_file: .env

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]

volumes:
  redis_data:
```

---

## 8. Deploy no Azure (notas)

Para rodar no Azure com Docker:
1. **Azure Container Apps** — opção mais simples, sobe o docker-compose direto
2. **Azure Kubernetes Service (AKS)** — opção para escala maior, requer conversão para Helm chart
3. **Azure Container Registry (ACR)** — repositório privado para as imagens Docker

Passos básicos com Container Apps:
```bash
az group create --name noc-ai-chat --location brazilsouth
az acr create --name nocaichat --resource-group noc-ai-chat --sku Basic
az containerapp env create --name noc-env --resource-group noc-ai-chat
```

---

## 9. Variáveis de Ambiente (.env.example)

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Zabbix
ZABBIX_URL=https://seu-zabbix.empresa.com/api_jsonrpc.php
ZABBIX_USER=noc-agent
ZABBIX_PASSWORD=

# Datadog
DATADOG_API_KEY=
DATADOG_APP_KEY=
DATADOG_SITE=datadoghq.com

# Grafana
GRAFANA_URL=https://seu-grafana.empresa.com
GRAFANA_TOKEN=

# ThousandEyes
THOUSANDEYES_TOKEN=

# Auth
JWT_SECRET=troque-por-uma-string-aleatoria-segura
JWT_EXPIRY_HOURS=8

# Redis
REDIS_URL=redis://redis:6379

# OpenAI (opcional, para STT/TTS avançado)
OPENAI_API_KEY=
```

---

## 10. Roadmap

| Fase | Escopo |
|------|--------|
| **v1 (MVP)** | Chat texto + voz, Zabbix + Datadog integrados, login simples, Docker |
| **v2** | Grafana + ThousandEyes, SSO/AD, notificações push, histórico persistente |
| **v3** | Ações nas ferramentas (silenciar alertas, criar tickets), integração PagerDuty/ServiceNow |

---

## 11. Critérios de Sucesso (v1)

- Agente responde perguntas sobre incidentes ativos em menos de 5 segundos
- Voz bidirecional funcional em Chrome/Edge desktop e Safari mobile
- Deploy completo via `docker-compose up` em menos de 10 minutos
- Suporte a pelo menos 10 usuários simultâneos sem degradação
