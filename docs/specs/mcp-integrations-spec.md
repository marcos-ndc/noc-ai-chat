# Spec: MCP Servers — Integrações NOC
**Versão:** 2.0 | **Data:** 2026-04-09 | **Status:** Implementado ✅

---

## Overview

4 MCP servers FastAPI independentes, cada um responsável por uma ferramenta NOC. Comunicação via HTTP interno na porta 8001 (rede Docker). Todos suportam: modo mock automático, SSL corporativo, logs estruturados, health endpoint com estado cacheado.

---

## Arquitetura Comum

```
POST /tools/<tool_name>   → executa a tool, retorna JSON
GET  /health              → status cached (não chama API externa a cada request)
GET  /debug/*             → endpoints de diagnóstico (dev only)
```

### Padrão de resposta de erro
```json
{
  "error": "mensagem legível",
  "error_type": "ConnectError",
  "tool": "nome_da_tool",
  "mode": "real"
}
```

### Variáveis de ambiente comuns
| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SSL_VERIFY` | `false` | Verificação SSL (false para proxy corporativo) |
| `*_TIMEOUT` | `10-15s` | Timeout das chamadas HTTP |

---

## MCP Zabbix

### Configuração
| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `ZABBIX_URL` | Sim (ou mock) | URL da API JSON-RPC do Zabbix |
| `ZABBIX_API_TOKEN` | Recomendado | Token permanente (Zabbix 7.x) |
| `ZABBIX_USER` | Fallback | Usuário (se sem API token) |
| `ZABBIX_PASSWORD` | Fallback | Senha |

### Tools implementadas (8)

| Tool | Input | Descrição |
|------|-------|-----------|
| `zabbix_list_organizations` | — | Lista clientes pela tag `Organization` com contagem de hosts |
| `zabbix_get_organization_summary` | `organization` | Resumo: hosts, disponibilidade, problemas por severidade |
| `zabbix_get_active_alerts` | `organization?`, `severity?`, `group?`, `host?`, `limit?` | Triggers ativos (trigger.get) |
| `zabbix_get_active_problems` | `organization?`, `severity?`, `group?`, `host?`, `limit?` | Problemas via problem.get (Zabbix 7.x) |
| `zabbix_get_host_status` | `hostname` | Status, interfaces, grupos, triggers ativos |
| `zabbix_get_trigger_history` | `hostname`, `hours?`, `severity?`, `limit?` | Histórico de eventos |
| `zabbix_get_item_latest` | `hostname`, `item_key` | Último valor de uma métrica |
| `zabbix_get_host_groups` | — | Lista grupos de hosts |

### Multi-cliente (tag Organization)
Hosts são identificados pela tag `Organization` no Zabbix. O helper `_get_hostids_by_org()` busca os hostids com `tag.operator=1` (contains) e filtra todas as queries pelo cliente.

### Severidades Zabbix
`not_classified(0)` → `information(1)` → `warning(2)` → `average(3)` → `high(4)` → `disaster(5)`

---

## MCP Datadog

### Configuração
| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `DATADOG_API_KEY` | Sim (ou mock) | API Key |
| `DATADOG_APP_KEY` | Sim (ou mock) | Application Key |
| `DATADOG_SITE` | Não | Padrão: `datadoghq.com` |
| `DATADOG_SSL_VERIFY` | Não | Padrão: `false` |

### Tools implementadas (5)

| Tool | Input | Descrição |
|------|-------|-----------|
| `datadog_get_active_monitors` | `status?`, `tags?`, `priority?` | Monitors por status (Alert/Warn/OK) |
| `datadog_get_metrics` | `metric`, `host?`, `from_minutes_ago?` | Timeseries de uma métrica |
| `datadog_get_logs` | `query?`, `from_minutes_ago?`, `limit?` | Logs com filtro DQL |
| `datadog_get_incidents` | `status?`, `severity?` | Incidentes ativos |
| `datadog_get_hosts` | `filter?`, `count?` | Hosts monitorados |

### Endpoints de diagnóstico
- `GET /debug/monitors` → chama `/api/v1/monitor` diretamente, retorna resposta raw

### Health com cache
```python
_auth_ok: bool = False   # definido no startup
# GET /health retorna _auth_ok sem chamar API Datadog a cada 30s
```

---

## MCP Grafana

### Configuração
| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `GRAFANA_URL` | Sim (ou mock) | URL base do Grafana |
| `GRAFANA_TOKEN` | Sim (ou mock) | Service Account token |
| `SSL_VERIFY` | Não | Padrão: `false` |

### Tools implementadas (2)

| Tool | Input | Descrição |
|------|-------|-----------|
| `grafana_get_firing_alerts` | `folder?` | Alertas disparando agora |
| `grafana_get_alert_rules` | `state?` | Regras de alerta configuradas |

---

## MCP ThousandEyes

### Configuração
| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `THOUSANDEYES_TOKEN` | Sim (ou mock) | Bearer token OAuth2 |
| `THOUSANDEYES_USER` | Fallback | Email (Basic Auth legado) |
| `THOUSANDEYES_PASSWORD` | Fallback | API token como senha |
| `THOUSANDEYES_AID` | Não | Account Group ID (multi-conta) |
| `SSL_VERIFY` | Não | Padrão: `false` |

### Tools implementadas (6)

| Tool | Input | Descrição |
|------|-------|-----------|
| `thousandeyes_list_tests` | — | Lista todos os testes com tipo, URL, intervalo |
| `thousandeyes_get_active_alerts` | `alert_type?`, `test_name?` | Alertas ativos filtráveis |
| `thousandeyes_get_test_results` | `test_id`, `window?` | Métricas com agregação (availability, latency, loss, jitter) |
| `thousandeyes_get_test_availability` | `test_name?`, `window?`, `threshold_pct?` | Disponibilidade de todos os testes |
| `thousandeyes_get_bgp_alerts` | — | Alertas BGP (hijacks, route leaks) |
| `thousandeyes_get_agents` | — | Agentes enterprise e cloud com localização |

### Endpoints por tipo de teste (API v7)
| Tipo | Endpoint | Campos retornados |
|------|----------|-------------------|
| `http-server` | `/test-results/{id}/http-server` | `availability`, `responseTime`, `loss` |
| `page-load` | `/test-results/{id}/page-load` | `availability`, `responseTime` |
| `dns-server` | `/test-results/{id}/dns-server` | `availability`, `resolutionTime` |
| `agent-to-server` | `/test-results/{id}/network/latency` | `avgLatency`, `loss`, `jitter` |
| `network` | `/test-results/{id}/network/latency` | `avgLatency`, `loss`, `jitter` |
| `bgp` | `/test-results/{id}/bgp/routes` | rotas, prefixos |

**Nota crítica:** `agent-to-server` usa `/network/latency`, **não** `/network/metrics` (retorna 404).

---

## Comportamento em Modo Mock

Todos os MCP servers detectam ausência de credenciais e retornam dados simulados realistas com prefixo `[MOCK]`. O modo mock é ativado automaticamente — sem necessidade de configuração explícita.

```python
MOCK_MODE = not bool(ZABBIX_URL)  # Zabbix
MOCK_MODE = not bool(DD_API_KEY)  # Datadog
MOCK_MODE = not bool(TE_TOKEN or (TE_BASIC_USER and TE_BASIC_PASS))  # ThousandEyes
```

---

## Non-Functional Requirements

| ID | Requisito | Meta | Status |
|----|-----------|------|--------|
| NFR-1 | Latência p95 Zabbix (rede interna) | < 3s | ✅ |
| NFR-2 | Latência p95 Datadog (cloud) | < 5s | ✅ |
| NFR-3 | Latência p95 ThousandEyes | < 5s | ✅ |
| NFR-4 | Cache de autenticação — sem re-auth por request | Obrigatório | ✅ |
| NFR-5 | Retry automático: 3 tentativas com backoff | Obrigatório | ✅ (tenacity) |
| NFR-6 | Health sem chamada API externa (estado cacheado) | Recomendado | ✅ Datadog |
| NFR-7 | SSL corporativo via `SSL_VERIFY=false` | Obrigatório | ✅ |
