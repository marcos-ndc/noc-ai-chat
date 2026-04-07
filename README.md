# NOC AI Chat

Agente de IA especializado em operações NOC com interface de chat por texto e voz.

## Stack
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS (PWA)
- **Backend:** Python + FastAPI + WebSockets
- **IA:** Claude API (Anthropic) + MCP Tools
- **Ferramentas NOC:** Zabbix, Datadog, Grafana, ThousandEyes

## Início Rápido
```bash
docker-compose up
```

## Documentação
- [Design Spec](docs/specs/2026-04-07-noc-ai-agent-chat-design.md)
- [Constituição do Projeto](docs/CONSTITUTION.md)
- [Spec Frontend](docs/specs/frontend-spec.md)
- [Tasks Frontend](docs/tasks/frontend-tasks.md)

## Branching
- `main` — produção (protegida)
- `feature/*` — novas features
- `fix/*` — correções
