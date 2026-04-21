# Spec: MCP Servers
**Versão:** 3.0 | **Data:** 2026-04-21 | **Status:** Implementado ✅

---

## Padrão comum

```
POST /tools/<tool_name>  → executa tool, retorna JSON
GET  /health             → status cacheado (sem chamar API externa)
```

- Porta interna Docker: **8001** para todos
- Mock automático quando credenciais ausentes
- SSL: `SSL_VERIFY=false` por padrão (proxy corporativo)
- Retries: tenacity com backoff

---

## Zabbix (8 tools)

| Tool | Input obrigatório | Descrição |
|------|-----------------|-----------|
| `zabbix_list_organizations` | — | Lista clientes pela tag Organization |
| `zabbix_get_organization_summary` | organization | Saúde do cliente (hosts, alertas, disponibilidade) |
| `zabbix_get_active_alerts` | — | Triggers ativos enriquecidos com _enrich_triggers() |
| `zabbix_get_active_problems` | — | Problemas via problem.get (Zabbix 7.x) |
| `zabbix_get_host_status` | hostname | Status completo: interfaces, grupos, triggers |
| `zabbix_get_trigger_history` | hostname | Histórico de eventos |
| `zabbix_get_item_latest` | hostname, item_key | Último valor de métrica |
| `zabbix_get_host_groups` | — | Lista grupos de hosts |

**Nota:** `_enrich_triggers()` converte trigger.get → `{severity_label, duration_minutes, hosts, lastchange_iso}`.

---

## Datadog (5 tools)

| Tool | Descrição |
|------|-----------|
| `datadog_get_active_monitors` | Monitors por status/tags |
| `datadog_get_metrics` | Timeseries de métrica |
| `datadog_get_logs` | Logs com DQL |
| `datadog_get_incidents` | Incidentes ativos |
| `datadog_get_hosts` | Hosts monitorados |

---

## Grafana (2 tools)

| Tool | Descrição |
|------|-----------|
| `grafana_get_firing_alerts` | Alertas disparando |
| `grafana_get_alert_rules` | Regras configuradas |

---

## ThousandEyes (6 tools)

| Tool | Descrição |
|------|-----------|
| `thousandeyes_list_tests` | Lista todos os testes |
| `thousandeyes_get_active_alerts` | Alertas ativos |
| `thousandeyes_get_test_results` | Métricas com agregação |
| `thousandeyes_get_test_availability` | Disponibilidade consolidada |
| `thousandeyes_get_bgp_alerts` | Hijacks e route leaks BGP |
| `thousandeyes_get_agents` | Agentes enterprise e cloud |

**Crítico:** `agent-to-server` usa `/network/latency` — NÃO `/network/metrics` (retorna 404).
