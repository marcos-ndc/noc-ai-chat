# 🖥️ NOC AI Chat

Agente de IA especializado em operações de NOC com interface de chat por texto e voz.  
Integra **Zabbix**, **Datadog**, **Grafana** e **ThousandEyes** via MCP Tools.

---

## ✨ Features

- 💬 **Chat com IA** — perguntas em linguagem natural sobre incidentes e métricas
- 🎤 **Voz bidirecional** — fale e ouça respostas (STT + TTS)
- 🔴 **Tempo real** — streaming token-a-token com indicador de ferramenta ativa
- 🧠 **Perfis adaptados** — N1, N2, Engenheiro, Gestor com respostas personalizadas
- 📱 **PWA** — instalável em desktop e mobile
- 🐳 **Docker-first** — `docker compose up` sobe tudo

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────┐
│           Frontend (React PWA)           │
│  Chat │ Voice Input (STT) │ Voice (TTS) │
└────────────────┬────────────────────────┘
                 │ WebSocket (streaming)
┌────────────────▼────────────────────────┐
│         Backend (FastAPI)               │
│    Agent Orchestrator (Claude API)       │
│  MCP Zabbix │ Datadog │ Grafana │ T.Eyes│
└────┬─────────┬──────────┬──────────┬───┘
     │         │          │          │
  Zabbix    Datadog    Grafana    ThousandEyes
   API        API        API         API
```

---

## 🚀 Início Rápido

### Pré-requisitos
- Docker + Docker Compose
- Node.js 20+ (para desenvolvimento)
- Python 3.8+ (para desenvolvimento)

### 1. Clone e configure
```bash
git clone https://github.com/marcos-ndc/noc-ai-chat.git
cd noc-ai-chat

# Setup automático
bash scripts/setup-dev.sh

# Ou manual:
cp .env.example .env
# Edite .env com suas API keys
```

### 2. Configure o `.env`
```env
# Obrigatório
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<gere com: openssl rand -hex 32>

# Opcional — MCP servers usam mock se vazios
ZABBIX_URL=https://seu-zabbix/api_jsonrpc.php
ZABBIX_USER=noc-agent
ZABBIX_PASSWORD=...

DATADOG_API_KEY=...
DATADOG_APP_KEY=...

GRAFANA_URL=https://seu-grafana
GRAFANA_TOKEN=...

THOUSANDEYES_TOKEN=...
```

### 3. Suba o stack
```bash
# Produção
make prod
# ou
docker compose up --build

# Desenvolvimento (hot-reload)
make dev
# ou
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### 4. Acesse
| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

## 👥 Usuários de Desenvolvimento

| Email | Senha | Perfil |
|-------|-------|--------|
| admin@noc.local | admin123 | Analista N2 |
| n1@noc.local | noc2024 | Analista N1 |
| eng@noc.local | eng2024 | Engenheiro |
| gestor@noc.local | mgr2024 | Gestor |

---

## 🛠️ Desenvolvimento

```bash
make help          # Lista todos os comandos

make test          # Roda todos os testes
make test-backend  # Testes Python (50 testes)
make test-frontend # Testes React
make lint          # TypeScript check

make logs          # Logs de todos os containers
make smoke         # Smoke test pós-deploy
```

### Branching
```bash
make branch-feature NAME=minha-feature   # → feature/minha-feature
make branch-fix NAME=meu-fix             # → fix/meu-fix
```

Commits seguem **Conventional Commits**:
```
feat: T005 implement chat message component
fix: T012 correct WebSocket reconnect logic
docs: update API configuration guide
test: add integration tests for auth endpoint
```

---

## 📁 Estrutura

```
noc-ai-chat/
├── frontend/          # React 18 + TypeScript + Tailwind (PWA)
├── backend/           # FastAPI + Claude API + WebSocket
│   ├── app/
│   │   ├── agent/     # Orchestrator, Session, Prompt, MCP Dispatcher
│   │   ├── auth/      # JWT + AuthService
│   │   ├── routers/   # /auth/login, /health
│   │   └── websocket/ # WS handler /ws/chat
│   └── tests/         # 50 testes (unit + integração)
├── mcp-servers/       # MCP servers independentes por ferramenta
│   ├── zabbix/
│   ├── datadog/
│   ├── grafana/
│   └── thousandeyes/
├── docs/
│   ├── specs/         # Especificações SDD
│   └── tasks/         # Task breakdowns TDD
├── scripts/
│   ├── setup-dev.sh   # Setup automático
│   └── smoke_test.py  # Smoke test pós-deploy
├── .github/workflows/ # CI/CD GitHub Actions
├── docker-compose.yml          # Produção
├── docker-compose.dev.yml      # Desenvolvimento
└── Makefile           # Comandos make
```

---

## 🔧 Configuração das APIs NOC

### Zabbix
1. **Administration → Users** → criar usuário `noc-agent`
2. API URL: `https://seu-zabbix/api_jsonrpc.php`
3. Testar: `curl -X POST <url> -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"user.login","params":{"username":"noc-agent","password":"<senha>"},"id":1}'`

### Datadog
1. **Organization Settings → API Keys** → criar chave `noc-agent`
2. **Organization Settings → Application Keys** → criar chave `noc-agent-app`

### Grafana
1. **Administration → Service Accounts** → criar conta `noc-agent` (Viewer)
2. Gerar token na service account criada

### ThousandEyes
1. **Account Settings → Security & Authentication → User API Tokens**
2. Gerar token OAuth Bearer

---

## 📊 Roadmap

| Versão | Escopo |
|--------|--------|
| **v1 MVP** ✅ | Chat + voz, Zabbix + Datadog + Grafana + ThousandEyes (mock), login simples |
| **v2** | SSO/AD, notificações push, histórico persistente entre sessões |
| **v3** | Ações nas ferramentas (silenciar alertas, criar tickets), PagerDuty/ServiceNow |

---

## 📄 Documentação

- [Constituição do Projeto](docs/CONSTITUTION.md)
- [Design Spec](docs/specs/2026-04-07-noc-ai-agent-chat-design.md)
- [Guia de Contribuição](CONTRIBUTING.md)
