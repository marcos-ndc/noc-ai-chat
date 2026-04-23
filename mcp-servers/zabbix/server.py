"""
MCP Server — Zabbix 7.x
Integração real com Zabbix via API JSON-RPC 2.0.
Suporta autenticação por API token (recomendado) e user/password.
Suporta filtro por tag Organization para ambientes multi-cliente.
Fallback automático para mock quando ZABBIX_URL não configurado.
"""
import os
import time
import asyncio
import logging
from typing import Optional, Any
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from tenacity import (
    retry, stop_after_attempt, wait_fixed,
    retry_if_exception_type, before_sleep_log
)

# ─── Configuração ─────────────────────────────────────────────────────────────

ZABBIX_URL       = os.getenv("ZABBIX_URL", "").rstrip("/")
ZABBIX_USER      = os.getenv("ZABBIX_USER", "")
ZABBIX_PASSWORD  = os.getenv("ZABBIX_PASSWORD", "")
ZABBIX_API_TOKEN = os.getenv("ZABBIX_API_TOKEN", "")
ZABBIX_TIMEOUT   = int(os.getenv("ZABBIX_TIMEOUT", "10"))

MOCK_MODE = not bool(ZABBIX_URL)

log = logging.getLogger("mcp-zabbix")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─── Severidade ───────────────────────────────────────────────────────────────

SEVERITY_INT = {
    "not_classified": 0,
    "information": 1,
    "warning": 2,
    "average": 3,
    "high": 4,
    "disaster": 5,
}
SEVERITY_LABEL = {v: k for k, v in SEVERITY_INT.items()}


# ─── Cliente Zabbix 7.x ───────────────────────────────────────────────────────

class ZabbixClient:
    def __init__(self):
        self._session_token: Optional[str] = None
        self._session_created: float = 0.0
        self._session_ttl: int = 3600
        self._client = httpx.AsyncClient(
            timeout=ZABBIX_TIMEOUT,
            verify=False,
            headers={"Content-Type": "application/json"},
        )

    @property
    def _auth(self) -> Optional[str]:
        if ZABBIX_API_TOKEN:
            return ZABBIX_API_TOKEN
        if self._session_token and (time.time() - self._session_created) < self._session_ttl:
            return self._session_token
        return None

    async def _ensure_auth(self) -> None:
        if ZABBIX_API_TOKEN:
            return
        if self._auth:
            return
        log.info("zabbix.login: autenticando via user.login")
        result = await self._rpc("user.login", {
            "username": ZABBIX_USER,
            "password": ZABBIX_PASSWORD,
        }, auth=None)
        self._session_token = result
        self._session_created = time.time()
        log.info("zabbix.login: autenticado com sucesso")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(httpx.HTTPError),
        before_sleep=before_sleep_log(log, logging.WARNING),
    )
    async def _rpc(self, method: str, params: dict, auth: Optional[str] = "auto") -> Any:
        if auth == "auto":
            auth = self._auth

        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        headers = {}
        if auth:
            if ZABBIX_API_TOKEN:
                headers["Authorization"] = f"Bearer {auth}"
            else:
                payload["auth"] = auth

        t0 = time.monotonic()
        resp = await self._client.post(ZABBIX_URL, json=payload, headers=headers)
        latency_ms = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        data = resp.json()
        log.info(f"zabbix.rpc method={method} latency={latency_ms:.0f}ms")

        if "error" in data:
            err = data["error"]
            if err.get("code") in (-32602, -32600):
                self._session_token = None
            raise ValueError(f"Zabbix API error {err.get('code')}: {err.get('data', err.get('message'))}")

        return data.get("result")

    async def call(self, method: str, params: dict) -> Any:
        await self._ensure_auth()
        return await self._rpc(method, params)

    async def get_version(self) -> str:
        return await self._rpc("apiinfo.version", {}, auth=None)

    async def close(self):
        await self._client.aclose()


_zabbix = ZabbixClient()


# ─── Helpers de tag ───────────────────────────────────────────────────────────

def _tag_filter(organization: Optional[str]) -> Optional[list]:
    """Monta filtro de tags para a API Zabbix quando organization é fornecida."""
    if not organization:
        return None
    return [{"tag": "Organization", "value": organization, "operator": "1"}]  # 1 = contains


async def _get_hostids_by_org(organization: str) -> list[str]:
    """Busca hostids de todos os hosts que têm tag Organization=<valor>."""
    hosts = await _zabbix.call("host.get", {
        "output": ["hostid"],
        "tags": [{"tag": "Organization", "value": organization, "operator": "1"}],
    })
    return [h["hostid"] for h in hosts]


# ─── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MOCK_MODE:
        try:
            version = await _zabbix.get_version()
            log.info(f"zabbix.startup: conectado versão={version}")
        except Exception as e:
            log.warning(f"zabbix.startup: aviso — não foi possível verificar versão: {e}")
    else:
        log.info("zabbix.startup: modo MOCK ativo (ZABBIX_URL não configurado)")
    yield
    await _zabbix.close()


app = FastAPI(title="MCP Zabbix", version="2.0.0", lifespan=lifespan)


# ─── Tool: list_organizations ─────────────────────────────────────────────────

@app.post("/tools/zabbix_list_organizations")
async def list_organizations(_: dict = {}):
    """
    Lista todos os clientes/organizações monitorados no Zabbix
    identificados pela tag 'Organization'.
    """
    if MOCK_MODE:
        return _mock_organizations()

    try:
        # Busca todos os hosts e suas tags
        hosts = await _zabbix.call("host.get", {
            "output": ["hostid", "host", "name", "status", "available"],
            "selectTags": "extend",
            "real_hosts": True,
        })

        # Extrai valores únicos da tag Organization
        orgs: dict[str, dict] = {}
        hosts_sem_org = 0

        for h in hosts:
            tags = h.get("tags", [])
            org_tag = next((t for t in tags if t.get("tag") == "Organization"), None)
            if org_tag:
                org_name = org_tag["value"]
                if org_name not in orgs:
                    orgs[org_name] = {"organization": org_name, "host_count": 0, "hosts": []}
                orgs[org_name]["host_count"] += 1
                orgs[org_name]["hosts"].append({
                    "host": h.get("host"),
                    "name": h.get("name"),
                    "available": {"0": "unknown", "1": "available", "2": "unavailable"}.get(
                        str(h.get("available", 0)), "unknown"
                    ),
                })
            else:
                hosts_sem_org += 1

        result = sorted(orgs.values(), key=lambda x: x["organization"])
        return {
            "total_organizations": len(result),
            "total_hosts_with_org": sum(o["host_count"] for o in result),
            "hosts_without_org_tag": hosts_sem_org,
            "organizations": result,
        }

    except Exception as e:
        return {"error": str(e), "tool": "zabbix_list_organizations"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _enrich_triggers(triggers: list) -> list:
    """Convert raw trigger.get response to enriched alert format."""
    import time as _time
    enriched = []
    for t in triggers:
        priority = str(t.get("priority", "0"))
        lastchange = int(t.get("lastchange", 0))
        now = int(_time.time())
        duration_minutes = (now - lastchange) // 60 if lastchange else 0

        hosts = [
            {"host": h.get("host", ""), "name": h.get("name", h.get("host", ""))}
            for h in t.get("hosts", [])
        ]

        # Extract organization from host tags if available
        organization = None
        for h in t.get("hosts", []):
            for tag in h.get("tags", []):
                if tag.get("tag", "").lower() == "organization":
                    organization = tag.get("value")
                    break

        enriched.append({
            "triggerid":       t.get("triggerid"),
            "description":     t.get("description", ""),
            "priority":        priority,
            "severity_label":  SEVERITY_LABEL.get(int(priority), "unknown"),
            "severity_int":    int(priority),
            "lastchange":      lastchange,
            "lastchange_iso":  _time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", _time.gmtime(lastchange)
            ) if lastchange else None,
            "duration_minutes": duration_minutes,
            "hosts":           hosts,
            "organization":    organization,
            "url":             t.get("url", ""),
            "comments":        t.get("comments", ""),
        })
    return enriched


# ─── Tool: get_active_alerts ─────────────────────────────────────────────────

class GetActiveAlertsInput(BaseModel):
    severity: Optional[str] = "warning"
    organization: Optional[str] = None   # ← NOVO: filtro por tag Organization
    group: Optional[str] = None
    host: Optional[str] = None
    limit: int = 30

@app.post("/tools/zabbix_get_active_alerts")
async def get_active_alerts(body: GetActiveAlertsInput):
    if MOCK_MODE:
        return _mock_alerts(body.organization)

    min_sev = SEVERITY_INT.get(body.severity or "warning", 2)

    params: dict = {
        "output": ["triggerid", "description", "priority", "lastchange", "comments"],
        "selectHosts": ["hostid", "host", "name", "status", "available"],
        "selectGroups": ["groupid", "name"],
        "selectTags": "extend",
        "sortfield": ["priority", "lastchange"],
        "sortorder": "DESC",
        "limit": body.limit,
        "only_true": True,
        "active": True,
        "min_severity": min_sev,
        "expandDescription": True,
        "expandComment": True,
    }

    if body.organization:
        hostids = await _get_hostids_by_org(body.organization)
        if not hostids:
            return {"count": 0, "alerts": [], "organization": body.organization,
                    "message": f"Nenhum host encontrado com tag Organization='{body.organization}'"}
        params["hostids"] = hostids

    if body.group:
        groups = await _zabbix.call("hostgroup.get", {
            "output": ["groupid"],
            "search": {"name": body.group},
        })
        if groups:
            params["groupids"] = [g["groupid"] for g in groups]

    if body.host:
        hosts = await _zabbix.call("host.get", {
            "output": ["hostid"],
            "filter": {"host": [body.host]},
        })
        if hosts:
            params["hostids"] = [h["hostid"] for h in hosts]

    try:
        triggers = await _zabbix.call("trigger.get", params)
        enriched = _enrich_triggers(triggers)
        return {"count": len(enriched), "alerts": enriched, "organization": body.organization}
    except Exception as e:
        return {"error": str(e), "tool": "zabbix_get_active_alerts"}


# ─── Tool: get_active_problems ───────────────────────────────────────────────

class GetActiveProblemsInput(BaseModel):
    severity: Optional[str] = "warning"
    organization: Optional[str] = None   # ← NOVO
    group: Optional[str] = None
    host: Optional[str] = None
    limit: int = 30

@app.post("/tools/zabbix_get_active_problems")
async def get_active_problems(body: GetActiveProblemsInput):
    if MOCK_MODE:
        return _mock_problems(body.organization)

    min_sev = SEVERITY_INT.get(body.severity or "warning", 2)

    params: dict = {
        "output": "extend",
        "selectAcknowledges": ["userid", "message", "clock"],
        "selectTags": "extend",
        "sortfield": ["eventid"],
        "sortorder": "DESC",
        "limit": body.limit,
        "severities": list(range(min_sev, 6)),
        "suppressed": False,
    }

    if body.organization:
        hostids = await _get_hostids_by_org(body.organization)
        if not hostids:
            return {"count": 0, "problems": [], "organization": body.organization,
                    "message": f"Nenhum host encontrado com tag Organization='{body.organization}'"}
        params["hostids"] = hostids

    if body.group:
        groups = await _zabbix.call("hostgroup.get", {
            "output": ["groupid"],
            "search": {"name": body.group},
        })
        if groups:
            params["groupids"] = [g["groupid"] for g in groups]

    if body.host:
        hosts = await _zabbix.call("host.get", {
            "output": ["hostid"],
            "filter": {"host": [body.host]},
        })
        if hosts:
            params["hostids"] = [h["hostid"] for h in hosts]

    try:
        problems = await _zabbix.call("problem.get", params)

        if problems:
            objectids = [p["objectid"] for p in problems]
            triggers = await _zabbix.call("trigger.get", {
                "output": ["triggerid", "description"],
                "selectHosts": ["host", "name"],
                "selectTags": "extend",
                "triggerids": objectids,
            })
            trigger_map = {t["triggerid"]: t for t in triggers}
            for p in problems:
                t = trigger_map.get(p["objectid"], {})
                p["trigger_description"] = t.get("description", "")
                p["hosts"] = t.get("hosts", [])
                # Extrai org da trigger tags se disponível
                host_tags = t.get("tags", [])
                org_tag = next((tg for tg in host_tags if tg.get("tag") == "Organization"), None)
                p["organization"] = org_tag["value"] if org_tag else body.organization
                sev_int = int(p.get("severity", 0))
                p["severity_label"] = SEVERITY_LABEL.get(sev_int, "unknown")
                clock = p.get("clock")
                if clock:
                    p["clock_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(clock)))
                    p["duration_minutes"] = int((time.time() - int(clock)) / 60)
                p["acknowledged"] = len(p.get("acknowledges", [])) > 0

        return {
            "count": len(problems),
            "problems": problems,
            "organization": body.organization,
        }
    except Exception as e:
        return {"error": str(e), "tool": "zabbix_get_active_problems"}


# ─── Tool: get_organization_summary ──────────────────────────────────────────

class GetOrgSummaryInput(BaseModel):
    organization: str   # valor da tag Organization

@app.post("/tools/zabbix_get_organization_summary")
async def get_organization_summary(body: GetOrgSummaryInput):
    """
    Resumo completo de um cliente: hosts, disponibilidade,
    problemas ativos por severidade.
    """
    if MOCK_MODE:
        return _mock_org_summary(body.organization)

    try:
        # 1. Hosts do cliente
        hosts = await _zabbix.call("host.get", {
            "output": ["hostid", "host", "name", "status", "available", "error"],
            "selectTags": "extend",
            "selectGroups": ["name"],
            "tags": [{"tag": "Organization", "value": body.organization, "operator": "1"}],
        })

        if not hosts:
            return {
                "organization": body.organization,
                "found": False,
                "message": f"Nenhum host com tag Organization='{body.organization}' encontrado.",
            }

        hostids = [h["hostid"] for h in hosts]

        # 2. Problemas ativos
        problems = await _zabbix.call("problem.get", {
            "output": ["eventid", "objectid", "name", "severity", "clock", "acknowledged"],
            "hostids": hostids,
            "severities": [2, 3, 4, 5],  # warning a disaster
            "suppressed": False,
        })

        # Contagem por severidade
        sev_count: dict[str, int] = {
            "warning": 0, "average": 0, "high": 0, "disaster": 0
        }
        for p in problems:
            sev = int(p.get("severity", 0))
            label = SEVERITY_LABEL.get(sev, "")
            if label in sev_count:
                sev_count[label] += 1

        # Status de disponibilidade dos hosts
        avail_map = {"0": "unknown", "1": "available", "2": "unavailable"}
        host_summary = []
        for h in hosts:
            host_summary.append({
                "host": h.get("host"),
                "name": h.get("name"),
                "available": avail_map.get(str(h.get("available", 0)), "unknown"),
                "groups": [g["name"] for g in h.get("groups", [])],
            })

        unavailable = sum(1 for h in host_summary if h["available"] == "unavailable")
        total_problems = len(problems)
        has_critical = sev_count["disaster"] > 0 or sev_count["high"] > 0

        return {
            "organization": body.organization,
            "found": True,
            "health_status": "CRITICAL" if sev_count["disaster"] > 0
                             else "HIGH" if sev_count["high"] > 0
                             else "WARNING" if sev_count["warning"] > 0 or sev_count["average"] > 0
                             else "OK",
            "hosts": {
                "total": len(hosts),
                "unavailable": unavailable,
                "available": len(hosts) - unavailable,
                "list": host_summary,
            },
            "problems": {
                "total": total_problems,
                "by_severity": sev_count,
                "has_critical": has_critical,
            },
        }

    except Exception as e:
        return {"error": str(e), "organization": body.organization}


# ─── Tool: get_host_status ───────────────────────────────────────────────────

class GetHostStatusInput(BaseModel):
    hostname: str

@app.post("/tools/zabbix_get_host_status")
async def get_host_status(body: GetHostStatusInput):
    if MOCK_MODE:
        return _mock_host_status(body.hostname)
    try:
        hosts = await _zabbix.call("host.get", {
            "output": ["hostid", "host", "name", "status", "available", "error"],
            "filter": {"host": [body.hostname]},
            "selectInterfaces": ["ip", "dns", "type", "available"],
            "selectGroups": ["groupid", "name"],
            "selectTags": "extend",
            "selectTriggers": {
                "output": ["triggerid", "description", "priority"],
                "only_true": True,
                "active": True,
            },
        })
        if not hosts:
            return {"found": False, "hostname": body.hostname}
        host = hosts[0]
        host["found"] = True
        host["available_label"] = {
            "0": "unknown", "1": "available", "2": "unavailable", "3": "degraded"
        }.get(str(host.get("available", 0)), "unknown")
        host["active_trigger_count"] = len(host.get("triggers", []))
        # Extrai Organization da tag
        tags = host.get("tags", [])
        org_tag = next((t for t in tags if t.get("tag") == "Organization"), None)
        host["organization"] = org_tag["value"] if org_tag else None
        return host
    except Exception as e:
        return {"error": str(e), "hostname": body.hostname}


# ─── Tool: get_trigger_history ───────────────────────────────────────────────

class GetTriggerHistoryInput(BaseModel):
    hostname: str
    hours: int = 24
    severity: Optional[str] = None
    limit: int = 50

@app.post("/tools/zabbix_get_trigger_history")
async def get_trigger_history(body: GetTriggerHistoryInput):
    if MOCK_MODE:
        return []
    try:
        time_from = int(time.time()) - (body.hours * 3600)
        min_sev = SEVERITY_INT.get(body.severity or "information", 0)
        events = await _zabbix.call("event.get", {
            "output": ["eventid", "clock", "name", "severity", "acknowledged", "r_eventid"],
            "selectHosts": ["host", "name"],
            "selectAcknowledges": ["message", "clock", "userid"],
            "selectTags": "extend",
            "source": 0,
            "value": 1,
            "time_from": time_from,
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": body.limit,
            "hosts": {"host": body.hostname},
            "severities": list(range(min_sev, 6)),
        })
        for e in events:
            sev_int = int(e.get("severity", 0))
            e["severity_label"] = SEVERITY_LABEL.get(sev_int, "unknown")
            clock = e.get("clock")
            if clock:
                e["clock_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(clock)))
            e["resolved"] = bool(e.get("r_eventid"))
        return events
    except Exception as e:
        return {"error": str(e), "hostname": body.hostname}


# ─── Tool: get_host_groups ───────────────────────────────────────────────────

@app.post("/tools/zabbix_get_host_groups")
async def get_host_groups(_: dict = {}):
    if MOCK_MODE:
        return [
            {"groupid": "1", "name": "Linux servers"},
            {"groupid": "2", "name": "Windows servers"},
            {"groupid": "3", "name": "Databases"},
        ]
    try:
        return await _zabbix.call("hostgroup.get", {
            "output": ["groupid", "name"],
            "real_hosts": True,
            "sortfield": "name",
        })
    except Exception as e:
        return {"error": str(e)}


# ─── Tool: get_item_latest ────────────────────────────────────────────────────

class GetItemLatestInput(BaseModel):
    hostname: str
    item_key: str

@app.post("/tools/zabbix_get_item_latest")
async def get_item_latest(body: GetItemLatestInput):
    if MOCK_MODE:
        return {"hostname": body.hostname, "item_key": body.item_key,
                "value": "42.5", "lastclock_iso": "2026-04-09T12:00:00Z", "mode": "mock"}
    try:
        items = await _zabbix.call("item.get", {
            "output": ["itemid", "name", "key_", "lastvalue", "lastclock", "units", "value_type", "status"],
            "filter": {"key_": [body.item_key]},
            "hosts": {"host": body.hostname},
            "limit": 1,
        })
        if not items:
            return {"found": False, "hostname": body.hostname, "item_key": body.item_key}
        item = items[0]
        lc = item.get("lastclock")
        if lc:
            item["lastclock_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(lc)))
        return item
    except Exception as e:
        return {"error": str(e)}


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    if MOCK_MODE:
        return {"status": "ok", "mode": "mock",
                "message": "Configure ZABBIX_URL para modo real"}
    try:
        t0 = time.monotonic()
        version = await _zabbix.get_version()
        latency_ms = (time.monotonic() - t0) * 1000
        return {
            "status": "ok", "mode": "real", "version": version,
            "latency_ms": round(latency_ms, 1),
            "auth_method": "api_token" if ZABBIX_API_TOKEN else "user_password",
        }
    except Exception as e:
        return {"status": "down", "error": str(e), "mode": "real"}


# ─── Mock data ────────────────────────────────────────────────────────────────

def _mock_organizations():
    return {
        "total_organizations": 3,
        "total_hosts_with_org": 8,
        "hosts_without_org_tag": 2,
        "organizations": [
            {"organization": "ClienteA", "host_count": 3,
             "hosts": [{"host": "srv-clienteA-01", "name": "Servidor 01", "available": "available"},
                       {"host": "srv-clienteA-02", "name": "Servidor 02", "available": "available"},
                       {"host": "srv-clienteA-db", "name": "Database", "available": "unavailable"}]},
            {"organization": "ClienteB", "host_count": 3,
             "hosts": [{"host": "srv-clienteB-web", "name": "Web Server", "available": "available"},
                       {"host": "srv-clienteB-app", "name": "App Server", "available": "available"},
                       {"host": "srv-clienteB-db", "name": "Database", "available": "available"}]},
            {"organization": "ClienteC", "host_count": 2,
             "hosts": [{"host": "srv-clienteC-01", "name": "Servidor 01", "available": "available"},
                       {"host": "srv-clienteC-02", "name": "Servidor 02", "available": "available"}]},
        ],
    }

def _mock_org_summary(org: str):
    return {
        "organization": org,
        "found": True,
        "health_status": "WARNING",
        "hosts": {
            "total": 3, "unavailable": 1, "available": 2,
            "list": [
                {"host": f"srv-{org}-01", "name": "Servidor 01", "available": "available", "groups": ["Linux servers"]},
                {"host": f"srv-{org}-02", "name": "Servidor 02", "available": "available", "groups": ["Linux servers"]},
                {"host": f"srv-{org}-db", "name": "Database", "available": "unavailable", "groups": ["Databases"]},
            ],
        },
        "problems": {
            "total": 2,
            "by_severity": {"warning": 1, "average": 1, "high": 0, "disaster": 0},
            "has_critical": False,
        },
    }

def _mock_alerts(organization: Optional[str] = None):
    alerts = [
        {
            "triggerid": "1001",
            "description": "[MOCK] CPU alta > 90% em web-server-01",
            "priority": "4", "severity_label": "high", "severity_int": 4,
            "lastchange_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()) - 1800)),
            "duration_minutes": 30,
            "hosts": [{"host": "web-server-01", "name": "Web Server 01"}],
            "organization": organization or "ClienteA",
        },
        {
            "triggerid": "1002",
            "description": "[MOCK] Disco cheio (>95%) em db-primary",
            "priority": "5", "severity_label": "disaster", "severity_int": 5,
            "lastchange_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()) - 300)),
            "duration_minutes": 5,
            "hosts": [{"host": "db-primary", "name": "Database Primary"}],
            "organization": organization or "ClienteB",
        },
    ]
    if organization:
        alerts = [a for a in alerts if a["organization"] == organization]
    return {"count": len(alerts), "alerts": alerts, "organization": organization}

def _mock_problems(organization: Optional[str] = None):
    return {
        "count": 1,
        "organization": organization,
        "problems": [
            {
                "eventid": "5001", "objectid": "1001",
                "clock_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()) - 1800)),
                "duration_minutes": 30,
                "name": "[MOCK] CPU alta em web-server-01",
                "severity": "4", "severity_label": "high",
                "acknowledged": False,
                "hosts": [{"host": "web-server-01"}],
                "organization": organization or "ClienteA",
            }
        ],
    }

def _mock_host_status(hostname: str):
    return {
        "found": True, "host": hostname, "name": f"{hostname} (mock)",
        "status": "0", "available": "1", "available_label": "available",
        "active_trigger_count": 1, "groups": [{"name": "Mock Group"}],
        "organization": "ClienteA",
    }
