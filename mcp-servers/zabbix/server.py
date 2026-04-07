"""
MCP Server — Zabbix 7.x
Integração real com Zabbix via API JSON-RPC 2.0.
Suporta autenticação por API token (recomendado) e user/password.
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

ZABBIX_URL      = os.getenv("ZABBIX_URL", "").rstrip("/")
ZABBIX_USER     = os.getenv("ZABBIX_USER", "")
ZABBIX_PASSWORD = os.getenv("ZABBIX_PASSWORD", "")
ZABBIX_API_TOKEN = os.getenv("ZABBIX_API_TOKEN", "")  # Preferido no 7.x
ZABBIX_TIMEOUT  = int(os.getenv("ZABBIX_TIMEOUT", "10"))

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
    """
    Cliente para Zabbix API JSON-RPC 2.0.
    Zabbix 7.x: autentica via API token permanente (preferido)
    ou session token via user.login.
    """

    def __init__(self):
        self._session_token: Optional[str] = None
        self._session_created: float = 0.0
        self._session_ttl: int = 3600  # 1h — renovar antes de expirar
        self._client = httpx.AsyncClient(
            timeout=ZABBIX_TIMEOUT,
            verify=False,  # muitos Zabbix internos têm cert auto-assinado
            headers={"Content-Type": "application/json"},
        )

    @property
    def _auth(self) -> Optional[str]:
        """Retorna o token de autenticação atual."""
        # API token permanente (Zabbix 7.x) — sem expiração
        if ZABBIX_API_TOKEN:
            return ZABBIX_API_TOKEN
        # Session token por user/password
        if self._session_token and (time.time() - self._session_created) < self._session_ttl:
            return self._session_token
        return None

    async def _ensure_auth(self) -> None:
        """Garante autenticação válida. Só usa user.login se não há API token."""
        if ZABBIX_API_TOKEN:
            return  # API token não precisa de login
        if self._auth:
            return  # session token ainda válido

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
        """Executa chamada JSON-RPC ao Zabbix."""
        if auth == "auto":
            auth = self._auth

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }

        # Zabbix 7.x: auth vai no header Authorization quando é API token
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
            # Token expirado → forçar re-login na próxima chamada
            if err.get("code") in (-32602, -32600):
                self._session_token = None
            raise ValueError(f"Zabbix API error {err.get('code')}: {err.get('data', err.get('message'))}")

        return data.get("result")

    async def call(self, method: str, params: dict) -> Any:
        """Chamada autenticada ao Zabbix."""
        await self._ensure_auth()
        return await self._rpc(method, params)

    async def get_version(self) -> str:
        result = await self._rpc("apiinfo.version", {}, auth=None)
        return result

    async def close(self):
        await self._client.aclose()


_zabbix = ZabbixClient()


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


# ─── Tool: get_active_alerts ─────────────────────────────────────────────────

class GetActiveAlertsInput(BaseModel):
    severity: Optional[str] = "warning"
    group: Optional[str] = None
    host: Optional[str] = None
    limit: int = 30

@app.post("/tools/zabbix_get_active_alerts")
async def get_active_alerts(body: GetActiveAlertsInput):
    if MOCK_MODE:
        return _mock_alerts()

    min_sev = SEVERITY_INT.get(body.severity or "warning", 2)

    params: dict = {
        "output": ["triggerid", "description", "priority", "lastchange", "comments"],
        "selectHosts": ["hostid", "host", "name", "status", "available"],
        "selectGroups": ["groupid", "name"],
        "sortfield": ["priority", "lastchange"],
        "sortorder": "DESC",
        "limit": body.limit,
        "only_true": True,       # apenas triggers com problema ativo
        "active": True,
        "min_severity": min_sev,
        "expandDescription": True,
        "expandComment": True,
    }

    if body.group:
        # Buscar groupid pelo nome
        groups = await _zabbix.call("hostgroup.get", {
            "output": ["groupid", "name"],
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
        return _enrich_triggers(triggers)
    except Exception as e:
        return {"error": str(e), "mode": "real", "tool": "zabbix_get_active_alerts"}


def _enrich_triggers(triggers: list) -> list:
    """Adiciona campos humanizados às triggers."""
    for t in triggers:
        sev_int = int(t.get("priority", 0))
        t["severity_label"] = SEVERITY_LABEL.get(sev_int, "unknown")
        t["severity_int"] = sev_int

        # Converte timestamp para ISO
        lc = t.get("lastchange")
        if lc:
            t["lastchange_iso"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(lc))
            )
            t["duration_minutes"] = int((time.time() - int(lc)) / 60)
    return triggers


# ─── Tool: get_active_problems ───────────────────────────────────────────────

class GetActiveProblemsInput(BaseModel):
    severity: Optional[str] = "warning"
    group: Optional[str] = None
    host: Optional[str] = None
    limit: int = 30

@app.post("/tools/zabbix_get_active_problems")
async def get_active_problems(body: GetActiveProblemsInput):
    """
    Zabbix 7.x: usa problem.get para obter problemas ativos (mais preciso que trigger.get).
    """
    if MOCK_MODE:
        return _mock_problems()

    min_sev = SEVERITY_INT.get(body.severity or "warning", 2)

    params: dict = {
        "output": "extend",
        "selectAcknowledges": ["userid", "message", "clock"],
        "selectTags": "extend",
        "sortfield": ["severity", "clock"],
        "sortorder": "DESC",
        "limit": body.limit,
        "severities": list(range(min_sev, 6)),
        "suppressed": False,
    }

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

        # Enriquecer com nome do host
        if problems:
            objectids = [p["objectid"] for p in problems]
            triggers = await _zabbix.call("trigger.get", {
                "output": ["triggerid", "description"],
                "selectHosts": ["host", "name"],
                "triggerids": objectids,
            })
            trigger_map = {t["triggerid"]: t for t in triggers}
            for p in problems:
                t = trigger_map.get(p["objectid"], {})
                p["trigger_description"] = t.get("description", "")
                p["hosts"] = t.get("hosts", [])
                sev_int = int(p.get("severity", 0))
                p["severity_label"] = SEVERITY_LABEL.get(sev_int, "unknown")
                clock = p.get("clock")
                if clock:
                    p["clock_iso"] = time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(clock))
                    )
                    p["duration_minutes"] = int((time.time() - int(clock)) / 60)
                p["acknowledged"] = len(p.get("acknowledges", [])) > 0

        return problems
    except Exception as e:
        return {"error": str(e), "mode": "real", "tool": "zabbix_get_active_problems"}


# ─── Tool: get_host_status ───────────────────────────────────────────────────

class GetHostStatusInput(BaseModel):
    hostname: str

@app.post("/tools/zabbix_get_host_status")
async def get_host_status(body: GetHostStatusInput):
    if MOCK_MODE:
        return _mock_host_status(body.hostname)

    try:
        hosts = await _zabbix.call("host.get", {
            "output": ["hostid", "host", "name", "status", "available",
                       "error", "ipmi_available", "snmp_available"],
            "filter": {"host": [body.hostname]},
            "selectInterfaces": ["ip", "dns", "type", "available"],
            "selectGroups": ["groupid", "name"],
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
            "0": "unknown", "1": "available",
            "2": "unavailable", "3": "degraded"
        }.get(str(host.get("available", 0)), "unknown")
        host["active_trigger_count"] = len(host.get("triggers", []))
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
            "source": 0,           # trigger events
            "value": 1,            # PROBLEM events
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
                e["clock_iso"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(clock))
                )
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
    item_key: str   # ex: "system.cpu.util", "vm.memory.size[available]"

@app.post("/tools/zabbix_get_item_latest")
async def get_item_latest(body: GetItemLatestInput):
    """Busca o último valor de um item de monitoramento."""
    if MOCK_MODE:
        return {"hostname": body.hostname, "item_key": body.item_key,
                "value": "42.5", "lastclock_iso": "2026-04-07T16:00:00Z", "mode": "mock"}

    try:
        items = await _zabbix.call("item.get", {
            "output": ["itemid", "name", "key_", "lastvalue", "lastclock",
                       "units", "value_type", "status"],
            "filter": {"key_": [body.item_key]},
            "hosts": {"host": body.hostname},
            "limit": 1,
        })

        if not items:
            return {"found": False, "hostname": body.hostname, "item_key": body.item_key}

        item = items[0]
        lc = item.get("lastclock")
        if lc:
            item["lastclock_iso"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(lc))
            )
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
            "status": "ok",
            "mode": "real",
            "version": version,
            "latency_ms": round(latency_ms, 1),
            "auth_method": "api_token" if ZABBIX_API_TOKEN else "user_password",
        }
    except Exception as e:
        return {"status": "down", "error": str(e), "mode": "real"}


# ─── Mock data ────────────────────────────────────────────────────────────────

def _mock_alerts():
    return [
        {
            "triggerid": "1001",
            "description": "[MOCK] CPU alta > 90% em web-server-01",
            "priority": "4", "severity_label": "high", "severity_int": 4,
            "lastchange": str(int(time.time()) - 1800),
            "lastchange_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                              time.gmtime(int(time.time()) - 1800)),
            "duration_minutes": 30,
            "hosts": [{"host": "web-server-01", "name": "Web Server 01"}],
        },
        {
            "triggerid": "1002",
            "description": "[MOCK] Disco cheio (>95%) em db-primary",
            "priority": "5", "severity_label": "disaster", "severity_int": 5,
            "lastchange": str(int(time.time()) - 300),
            "lastchange_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                              time.gmtime(int(time.time()) - 300)),
            "duration_minutes": 5,
            "hosts": [{"host": "db-primary", "name": "Database Primary"}],
        },
    ]

def _mock_problems():
    return [
        {
            "eventid": "5001",
            "objectid": "1001",
            "clock": str(int(time.time()) - 1800),
            "clock_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                         time.gmtime(int(time.time()) - 1800)),
            "duration_minutes": 30,
            "name": "[MOCK] CPU alta em web-server-01",
            "severity": "4", "severity_label": "high",
            "acknowledged": False,
            "hosts": [{"host": "web-server-01"}],
        },
    ]

def _mock_host_status(hostname: str):
    return {
        "found": True,
        "host": hostname,
        "name": f"{hostname} (mock)",
        "status": "0",
        "available": "1",
        "available_label": "available",
        "active_trigger_count": 1,
        "groups": [{"name": "Mock Group"}],
    }
