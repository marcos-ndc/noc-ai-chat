# NOC AI Chat 🤖

Agente de IA especializado em operações NOC com interface de chat por texto e voz.
Integra Zabbix, Datadog, Grafana e ThousandEyes em uma única interface conversacional.

[![CI](https://github.com/marcos-ndc/noc-ai-chat/actions/workflows/ci.yml/badge.svg)](https://github.com/marcos-ndc/noc-ai-chat/actions/workflows/ci.yml)

---

## 🏗️ Arquitetura

```
Frontend (React PWA)  ←→  Backend (FastAPI + Claude API)  ←→  MCP Servers  ←→  APIs NOC
```

**Stack:** React 18 · TypeScript · Vite · Tailwind CSS · FastAPI · Python 3.12 · Redis 7 · Docker

---

## 🚀 Início Rápido

```bash
git clone https://github.com/marcos-ndc/noc-ai-chat.git
cd noc-ai-chat
cp .env.example .env
# Edite .env e adicione: ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build
```

Acesse: **http://localhost:3000**

**Usuários padrão (dev):**

| Email | Senha | Perfil |
|-------|-------|--------|
| admin@noc.local | admin123 | Analista N2 |
| n1@noc.local | noc2024 | Analista N1 |
| eng@noc.local | eng2024 | Engenheiro |
| gestor@noc.local | mgr2024 | Gestor |

---

## 🔧 Configuração das APIs NOC

### Zabbix
1. Crie usuário `noc-agent` em **Administration > Users** (papel Read-Only ou Super Admin)
2. Configure no `.env`: `ZABBIX_URL`, `ZABBIX_USER`, `ZABBIX_PASSWORD`

### Datadog
1. **Organization Settings > API Keys** → nova chave `noc-agent`
2. **Organization Settings > Application Keys** → nova chave `noc-agent-app`
3. Configure: `DATADOG_API_KEY`, `DATADOG_APP_KEY`, `DATADOG_SITE`

### Grafana
1. **Administration > Service Accounts** → criar `noc-agent` (Viewer) → gerar token
2. Configure: `GRAFANA_URL`, `GRAFANA_TOKEN`

### ThousandEyes
1. **Account Settings > User API Tokens** → gerar OAuth Bearer Token
2. Configure: `THOUSANDEYES_TOKEN`

> Sem credenciais configuradas, os MCP servers usam **dados mock** automaticamente.

---

## 🧪 Testes

```bash
# Backend (unitários + integração)
cd backend && pip install -r requirements.txt && pytest tests/ -v

# Frontend (TypeScript + unit tests)
cd frontend && npm install --legacy-peer-deps && npx tsc --noEmit && npm test

# Smoke test (stack rodando)
python scripts/smoke_test.py
```

---

## ☁️ Deploy Azure

```bash
az group create --name noc-ai-chat --location brazilsouth
az acr create --name nocaichat --resource-group noc-ai-chat --sku Basic
az acr login --name nocaichat
docker compose build
# push images e deploy via Container Apps
```

---

## 📁 Estrutura

```
├── frontend/          # React PWA (componentes, hooks, páginas)
├── backend/           # FastAPI (agent, auth, websocket, routers)
├── mcp-servers/       # Zabbix · Datadog · Grafana · ThousandEyes
├── scripts/           # smoke_test.py
├── docs/              # Specs SDD, tasks, constituição
└── .github/workflows/ # CI/CD (testes + docker build)
```

---

## 📋 Roadmap

| v1 (atual) | v2 | v3 |
|---|---|---|
| Chat texto + voz, 4 ferramentas NOC, login simples, Docker | SSO/AD, notificações push, histórico persistente | Ações nas ferramentas, PagerDuty/ServiceNow |

---

## 📄 Docs

- [Constituição do Projeto](docs/CONSTITUTION.md) · [Design Spec](docs/specs/2026-04-07-noc-ai-agent-chat-design.md) · [CONTRIBUTING](CONTRIBUTING.md)
