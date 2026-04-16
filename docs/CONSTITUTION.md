# NOC AI Chat — Project Constitution
**Versão:** 2.0 | **Data:** 2026-04-09 | **Anterior:** 1.0 (2026-04-07)

Documento não-negociável que governa todo o desenvolvimento do projeto.
Specs, planos e tasks não podem contradizer esta constituição sem revisão explícita.

---

## 1. Arquitetura

- **Estilo:** Frontend SPA desacoplado do backend via WebSocket + REST
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS (PWA)
- **Backend:** Python 3.12 + FastAPI + AsyncAnthropic (streaming real token a token)
- **Agente:** Claude claude-sonnet-4-20250514 com loop agêntico e MCP tools
- **MCP Servers:** 4 servidores FastAPI independentes (Zabbix, Datadog, Grafana, ThousandEyes)
- **Containers:** Tudo dockerizado — `make dev` sobe 100% do stack
- **Cloud-agnostic:** Nenhuma dependência de provider específico; Azure preferencial para deploy

### Fluxo de dados
```
Browser → WebSocket → Backend (FastAPI/AsyncAnthropic)
                            → MCP Zabbix       → Zabbix API JSON-RPC
                            → MCP Datadog      → Datadog API v1/v2
                            → MCP Grafana      → Grafana HTTP API
                            → MCP ThousandEyes → ThousandEyes API v7
                    → Redis (sessões, histórico 50 turnos, TTL 24h)
```

### Portas internas Docker (comunicação entre containers)
Todos os MCP servers escutam na **porta 8001** internamente.
O backend se comunica com eles via nome do serviço Docker, sempre na porta 8001.

---

## 2. Stack Permitido

### Frontend

| Categoria | Tecnologia | Versão |
|-----------|-----------|--------|
| Framework | React | 18.x |
| Linguagem | TypeScript | 5.x (strict) |
| Build | Vite | 5.x |
| Estilo | Tailwind CSS | 3.x |
| Estado global | Zustand | 4.x |
| Gráficos | Recharts + react-is | 2.x |
| WebSocket | nativo (browser API) | — |
| STT | Web Speech API | — |
| TTS | Web Speech API | — |
| Markdown | react-markdown + remark-gfm | 9.x |
| HTTP | fetch nativo | — |
| Testes | Vitest + Testing Library | — |
| PWA | vite-plugin-pwa | — |

**Proibido:** Redux, jQuery, Bootstrap, MUI, Ant Design, CSS-in-JS.

**Nota:** `react-is` é peer dependency obrigatória do Recharts. Deve estar em `package.json`.

### Backend / MCP Servers

| Categoria | Tecnologia | Versão |
|-----------|-----------|--------|
| Framework | FastAPI | 0.115+ |
| Linguagem | Python | 3.12+ |
| IA | anthropic (AsyncAnthropic) | 0.34+ |
| HTTP client | httpx (AsyncClient) | — |
| Cache/sessão | Redis (redis.asyncio) | 7.x |
| Auth | python-jose + bcrypt | — |
| Validação | pydantic + pydantic-settings | 2.x |
| Logs | structlog (JSON) | — |
| Retries | tenacity | — |

**Regra crítica:** Usar sempre `AsyncAnthropic` — nunca `Anthropic` síncrono. Chamada síncrona bloqueia o event loop e impede atender outros requests durante a chamada à API (que pode demorar 10-30s).

---

## 3. Git & Branching

- Branch principal: `main`
- Features: `feature/<nome-descritivo>`
- Bugs: `fix/<nome-descritivo>`
- Docs: `docs/<nome-descritivo>`
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`)
- PRs requerem: testes passando + zero erros TypeScript
- Merge via `--no-ff` para manter histórico legível

---

## 4. Qualidade de Código

- TypeScript strict mode — zero `any` implícito
- `tsc --noEmit` deve passar com 0 erros antes de qualquer merge
- `python3 -m py_compile` deve passar em todos os arquivos `.py`
- Componentes máximo 200 linhas
- Hooks máximo 100 linhas
- Nomes em inglês no código, comentários em português

---

## 5. Testes

- Backend: cobertura mínima 70% para lógica de negócio
- Frontend: ao menos 1 teste por hook crítico
- `make test` deve passar completamente antes de merge para main
- Baseline atual: **39 testes backend passando**

---

## 6. Segurança

- Zero secrets no frontend — apenas URLs públicas em variáveis de ambiente
- JWT armazenado apenas em Zustand (memória) — nunca localStorage
- HTTPS obrigatório em produção
- `ANTHROPIC_SSL_VERIFY=false` e `SSL_VERIFY=false` permitidos apenas com proxy corporativo documentado
- Chaves mascaradas nos logs: apenas primeiros 8 e últimos 4 caracteres

---

## 7. Proxy Corporativo

Ambientes com inspeção SSL corporativa requerem:

```env
ANTHROPIC_SSL_VERIFY=false   # API Anthropic
SSL_VERIFY=false              # MCP servers externos
```

Ver `docs/CORPORATE-PROXY.md` para configuração com certificado CA corporativo.

---

## 8. Performance

- First Contentful Paint < 2s
- Bundle principal < 300KB gzipped (baseline: ~109KB)
- Tempo até primeiro token (TTFT) < 3s
- Latência MCP tool call < 2s por ferramenta
- Lighthouse score ≥ 85

---

## 9. Internacionalização

- Interface em português (pt-BR)
- Mensagens de erro e logs do agente em pt-BR
- Estrutura preparada para i18n futuro

---

## 10. Docker

- Dockerfile multi-stage para frontend (build + nginx)
- `make dev` para desenvolvimento com hot-reload
- Todos os containers com healthcheck definido
- Comunicação interna sempre na porta **8001** para MCP servers
- Portas host: 3000 (frontend), 8000 (backend), 6379 (Redis), 8001-8004 (MCP externos)
- `environment:` em docker-compose sempre com valores reais (nunca apenas comentários — YAML inválido)

---

## 11. Variáveis de Ambiente Obrigatórias

| Variável | Serviço | Obrigatório | Observação |
|----------|---------|-------------|------------|
| `ANTHROPIC_API_KEY` | Backend | ✅ | Sem ela o agente não responde |
| `JWT_SECRET` | Backend | ✅ | `openssl rand -hex 32` |
| `ZABBIX_URL` | MCP Zabbix | Opcional | Mock se ausente |
| `ZABBIX_API_TOKEN` | MCP Zabbix | Opcional | Recomendado sobre user/password |
| `DATADOG_API_KEY` | MCP Datadog | Opcional | Mock se ausente |
| `DATADOG_APP_KEY` | MCP Datadog | Opcional | |
| `THOUSANDEYES_TOKEN` | MCP ThousandEyes | Opcional | Bearer OAuth2 |
| `GRAFANA_URL` | MCP Grafana | Opcional | Mock se ausente |
| `GRAFANA_TOKEN` | MCP Grafana | Opcional | |

Copie `.env.example` para `.env` e preencha antes de `make dev`.
