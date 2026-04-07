"""
MCP Server — Zabbix
Expõe tools para o agente consultar o Zabbix via API JSON-RPC.
"""
import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import os

app = FastAPI(title="MCP Zabbix", version="1.0.0")

ZABBIX_URL  = os.getenv("ZABBIX_URL", "")
ZABBIX_USER = os.getenv("ZABBIX_USER", "")
ZABBIX_PASS = os.getenv("ZABBIX_PASSWORD", "")

_auth_token: Optional[str] = None


async def _zabbix_rpc(method: str, params: dict) -> dict:
    global _auth_token
    client = httpx.AsyncClient(timeout=10.0, verify=False)

    # Auto-login if needed
    if _auth_token is None and method != "user.login":
        login_resp = await client.post(ZABBIX_URL, json={
            "jsonrpc": "2.0", "method": "user.login",
            "params": {"username": ZABBIX_USER, "password": ZABBIX_PASS},
            "id": 1,
        })
        _auth_token = login_resp.json().get("result")

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "auth": _auth_token,
        "id": 1,
    }
    resp = await client.post(ZABBIX_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        _auth_token = None  # force re-login on next call
        return {"error": data["error"]}
    return data.get("result", {})


# ─── Severity map ────────────────────────────────────────────────────────────
SEVERITY_MAP = {"info": 1, "warning": 2, "average": 3, "high": 4, "disaster": 5}


# ─── Tool: get_active_alerts ─────────────────────────────────────────────────
class GetActiveAlertsInput(BaseModel):
    severity: Optional[str] = "warning"
    group: Optional[str] = None
    limit: int = 20

@app.post("/tools/zabbix_get_active_alerts")
async def get_active_alerts(body: GetActiveAlertsInput):
    if not ZABBIX_URL:
        return _mock_alerts()

    params: dict = {
        "output": ["triggerid", "description", "priority", "lastchange"],
        "sortfield": "priority",
        "sortorder": "DESC",
        "limit": body.limit,
        "only_true": 1,
        "active": 1,
        "selectHosts": ["host", "name"],
        "min_severity": SEVERITY_MAP.get(body.severity or "warning", 2),
    }
    if body.group:
        params["groupids"] = await _get_group_id(body.group)

    return await _zabbix_rpc("trigger.get", params)


async def _get_group_id(group_name: str) -> list:
    result = await _zabbix_rpc("hostgroup.get", {
        "output": ["groupid"],
        "filter": {"name": [group_name]},
    })
    return [g["groupid"] for g in result] if isinstance(result, list) else []


# ─── Tool: get_host_status ───────────────────────────────────────────────────
class GetHostStatusInput(BaseModel):
    hostname: str

@app.post("/tools/zabbix_get_host_status")
async def get_host_status(body: GetHostStatusInput):
    if not ZABBIX_URL:
        return {"host": body.hostname, "status": "mock", "available": 1}

    return await _zabbix_rpc("host.get", {
        "output": ["hostid", "host", "name", "status", "available"],
        "filter": {"host": [body.hostname]},
    })


# ─── Tool: get_trigger_history ───────────────────────────────────────────────
class GetTriggerHistoryInput(BaseModel):
    hostname: str
    hours: int = 24
    severity: Optional[str] = None

@app.post("/tools/zabbix_get_trigger_history")
async def get_trigger_history(body: GetTriggerHistoryInput):
    if not ZABBIX_URL:
        return []

    import time
    time_from = int(time.time()) - (body.hours * 3600)
    params: dict = {
        "output": "extend",
        "time_from": time_from,
        "sortfield": "clock",
        "sortorder": "DESC",
        "limit": 50,
        "selectHosts": ["host"],
        "filter": {"hosts": [{"host": body.hostname}]},
    }
    if body.severity:
        params["min_severity"] = SEVERITY_MAP.get(body.severity, 2)

    return await _zabbix_rpc("event.get", params)


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    if not ZABBIX_URL:
        return {"status": "ok", "mode": "mock"}
    try:
        await _zabbix_rpc("apiinfo.version", {})
        return {"status": "ok"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


# ─── Mock data (when Zabbix not configured) ───────────────────────────────────
def _mock_alerts():
    return [
        {
            "triggerid": "1001",
            "description": "[MOCK] CPU alta em web-server-01",
            "priority": "4",
            "lastchange": "1712345678",
            "hosts": [{"host": "web-server-01", "name": "Web Server 01"}],
        },
        {
            "triggerid": "1002",
            "description": "[MOCK] Disco cheio em db-primary",
            "priority": "5",
            "lastchange": "1712340000",
            "hosts": [{"host": "db-primary", "name": "Database Primary"}],
        },
    ]
