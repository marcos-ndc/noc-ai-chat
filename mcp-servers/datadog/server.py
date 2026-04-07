"""
MCP Server — Datadog
Expõe tools para o agente consultar o Datadog via API REST.
"""
import os
from typing import Optional
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MCP Datadog", version="1.0.0")

DD_API_KEY = os.getenv("DATADOG_API_KEY", "")
DD_APP_KEY = os.getenv("DATADOG_APP_KEY", "")
DD_SITE    = os.getenv("DATADOG_SITE", "datadoghq.com")
DD_BASE    = f"https://api.{DD_SITE}"

_HEADERS = {
    "DD-API-KEY": DD_API_KEY,
    "DD-APPLICATION-KEY": DD_APP_KEY,
    "Content-Type": "application/json",
}


async def _dd_get(path: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{DD_BASE}{path}", headers=_HEADERS, params=params)
        resp.raise_for_status()
        return resp.json()


# ─── Tool: get_active_monitors ───────────────────────────────────────────────
class GetMonitorsInput(BaseModel):
    status: Optional[str] = "Alert"
    tags: Optional[list[str]] = None
    priority: Optional[int] = None

@app.post("/tools/datadog_get_active_monitors")
async def get_active_monitors(body: GetMonitorsInput):
    if not DD_API_KEY:
        return _mock_monitors()
    params: dict = {"monitor_status": body.status or "Alert", "page_size": 30}
    if body.tags:
        params["tags"] = ",".join(body.tags)
    if body.priority:
        params["priority"] = body.priority
    return await _dd_get("/api/v1/monitor", params)


# ─── Tool: get_metrics ───────────────────────────────────────────────────────
class GetMetricsInput(BaseModel):
    metric: str
    host: Optional[str] = None
    from_minutes_ago: int = 60

@app.post("/tools/datadog_get_metrics")
async def get_metrics(body: GetMetricsInput):
    if not DD_API_KEY:
        return {"series": [], "note": "Mock mode — Datadog não configurado"}
    import time
    now = int(time.time())
    query = body.metric
    if body.host:
        query += f"{{host:{body.host}}}"
    params = {"query": query, "from": now - body.from_minutes_ago * 60, "to": now}
    return await _dd_get("/api/v1/query", params)


# ─── Tool: get_incidents ─────────────────────────────────────────────────────
class GetIncidentsInput(BaseModel):
    status: Optional[str] = "active"
    severity: Optional[str] = None

@app.post("/tools/datadog_get_incidents")
async def get_incidents(body: GetIncidentsInput):
    if not DD_API_KEY:
        return _mock_incidents()
    params: dict = {}
    if body.status:
        params["filter[status]"] = body.status
    return await _dd_get("/api/v2/incidents", params)


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    if not DD_API_KEY:
        return {"status": "ok", "mode": "mock"}
    try:
        await _dd_get("/api/v1/validate")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


def _mock_monitors():
    return [
        {"id": 2001, "name": "[MOCK] High CPU on prod-app-01", "status": "Alert",
         "priority": 1, "tags": ["env:prod"]},
        {"id": 2002, "name": "[MOCK] DB Connection Pool Exhausted", "status": "Alert",
         "priority": 2, "tags": ["env:prod", "service:database"]},
    ]

def _mock_incidents():
    return {"data": [
        {"id": "3001", "attributes": {"title": "[MOCK] API latency degradation",
         "status": "active", "severity": "SEV-2"}},
    ]}
