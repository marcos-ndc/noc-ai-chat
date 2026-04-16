# NOC AI Chat — Design Spec
**Versão:** 2.0 | **Data:** 2026-04-09 | **Status:** Implementado ✅

---

## 1. Visão Geral

Aplicação web responsiva (PWA) de chat com agente de IA especializado em operações de NOC. O agente consulta Zabbix, Datadog, Grafana e ThousandEyes em tempo real via MCP tools e responde com streaming token-a-token, gráficos interativos e linguagem adaptada ao perfil do usuário.

### Objetivos alcançados na v1
- ✅ Interface conversacional única para todas as ferramentas NOC
- ✅ Respostas em streaming real (não fake chunking)
- ✅ Gráficos interativos Recharts renderizados inline
- ✅ Suporte a voz bidirecional (STT + TTS)
- ✅ Multi-cliente via tag Organization no Zabbix
- ✅ Funcionando em ambiente corporativo com proxy SSL

### Fora do escopo (v1)
- Automação de ações (silenciar alertas, criar tickets) → v3
- SSO/AD corporativo → v2
- App mobile nativo (PWA cobre mobile)
- Notificações push → v2

---

## 2. Usuários e Perfis

| Perfil | Comportamento do Agente |
|--------|------------------------|
| N1 | Linguagem simples, passo a passo, sempre indica quando escalar |
| N2 | Técnico moderado, diagnóstico completo com evidências |
| engineer | Totalmente técnico, dados brutos, análise de causa raiz |
| manager | Visão executiva, impacto de negócio, ETA de resolução |

Perfil detectado pelo JWT — system prompt adaptado automaticamente em cada chamada.

---

## 3. Arquitetura Final

```
┌─────────────────────────────────────────────────────────────┐
│                  FRONTEND (React 18 PWA)                     │
│  LoginPage │ ChatPage │ Charts (Recharts) │ Voice (STT/TTS)  │
└─────────────────────────┬───────────────────────────────────┘
                          │ WebSocket (streaming real)
┌─────────────────────────▼───────────────────────────────────┐
│              BACKEND (FastAPI + AsyncAnthropic)              │
│   AgentOrchestrator → messages.stream() → agent_token       │
│   MCPDispatcher → http://mcp-<service>:8001/tools/<tool>     │
│   SessionManager → Redis TTL 24h, 50 turnos                  │
└──────┬────────────┬──────────────┬────────────────┬─────────┘
       │            │              │                │
  MCP Zabbix   MCP Datadog   MCP Grafana   MCP ThousandEyes
  (8 tools)    (5 tools)     (2 tools)     (6 tools)
  :8001 int    :8001 int     :8001 int     :8001 int
  :8001 ext    :8002 ext     :8003 ext     :8004 ext
```

---

## 4. Componentes Implementados

### Frontend
- **LoginPage:** form validado, redireciona apenas em sucesso
- **ChatPage:** orquestra WS, mensagens, ferramentas ativas, voice
- **ChatMessage / AgentContent:** markdown + gráficos Recharts intercalados
- **ChatInput:** textarea auto-resize, voz, atalhos de teclado
- **Header:** perfil do usuário, status WS, logout
- **StatusIndicator:** ícone animado da ferramenta em uso
- **NocCharts:** 6 componentes com tema NOC escuro
- **chartParser:** parser de blocos `chart JSON` nas mensagens

### Backend
- **AgentOrchestrator:** loop agêntico, AsyncAnthropic, streaming real
- **MCPDispatcher:** roteamento por prefixo (zabbix_, datadog_, etc.)
- **SessionManager:** Redis, trim de histórico, role mapping correto
- **ConnectionManager:** WebSocket por connection_id
- **AuthService:** bcrypt direto, JWT, 4 seed users

### MCP Servers
- **mcp-zabbix:** JSON-RPC 2.0, API token, multi-cliente via tag Organization
- **mcp-datadog:** API v1/v2, tenacity retry, health cacheado
- **mcp-grafana:** HTTP API, modo mock
- **mcp-thousandeyes:** API v7, Bearer/Basic auth, endpoints corretos por tipo

---

## 5. Gráficos Interativos

O agente emite blocos ` ```chart {...} ``` ` com JSON estruturado. O frontend detecta, parseia e renderiza componentes Recharts interativos inline.

### Tipos suportados

| chartType | Componente | Caso de uso |
|-----------|------------|-------------|
| `availability` | AvailabilityChart | Disponibilidade % ao longo do tempo |
| `response_time` | ResponseTimeChart | Latência HTTP em ms |
| `packet_loss` | PacketLossChart | % perda de pacotes |
| `network_latency` | NetworkLatencyChart | Latência de rede (avg/min/max/jitter) |
| `latency_simulation` | NetworkLatencyChart | Alias — renderiza igual ao network_latency |
| `multi_metric` | MetricDashboard | Painel com availability + response_time + packet_loss |
| `availability_summary` | AvailabilitySummaryChart | Barras horizontais com todos os testes |

### Exemplo de bloco gerado pelo agente
```json
{
  "chartType": "network_latency",
  "testName": "SAP - tereos-sap.empresa.net",
  "window": "6h",
  "avg": 35.5,
  "min": 12.0,
  "max": 180.0,
  "jitter": 2.3,
  "points": [
    {"time": "06:00", "value": 32},
    {"time": "12:00", "value": 45},
    {"time": "18:00", "value": 38}
  ]
}
```

---

## 6. Usuários Seed (Desenvolvimento)

| Email | Senha | Perfil |
|-------|-------|--------|
| `admin@noc.local` | `admin123` | N2 |
| `n1@noc.local` | `noc2024` | N1 |
| `eng@noc.local` | `eng2024` | Engineer |
| `gestor@noc.local` | `mgr2024` | Manager |

---

## 7. Endpoints API

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/auth/login` | Autenticação, retorna JWT + User |
| GET | `/health` | Status de todos os serviços |
| GET | `/debug/config` | Variáveis de ambiente mascaradas |
| WS | `/ws/chat?token=<jwt>` | Chat com streaming |

---

## 8. Eventos WebSocket

### Frontend → Backend
```json
{ "type": "user_message", "content": "...", "sessionId": "abc123" }
{ "type": "ping" }
```

### Backend → Frontend
```json
{ "type": "tool_start", "tool": "zabbix" }
{ "type": "tool_end", "tool": "zabbix" }
{ "type": "agent_token", "messageId": "abc", "content": "..." }
{ "type": "agent_done", "messageId": "abc" }
{ "type": "error", "error": "mensagem legível" }
{ "type": "pong" }
```
