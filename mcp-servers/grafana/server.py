"""
MCP Server — Grafana
Expõe tools para o agente consultar alertas e regras no Grafana.
"""
import os

# Proxy corporativo: SSL_VERIFY=false para ambientes com inspeção SSL
_SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() != "false"
from typing import Optional
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MCP Grafana", version="1.0.0")

GRAFANA_URL   = os.getenv("GRAFANA_URL", "")
GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN", "")
_HEADERS = {"Authorization": f"Bearer {GRAFANA_TOKEN}", "Content-Type": "application/json"}


async def _grafana_get(path: str, params: Optional[dict] = None) -> dict | list:
    async with httpx.AsyncClient(timeout=10.0, verify=_SSL_VERIFY) as client:
        resp = await client.get(f"{GRAFANA_URL}{path}", headers=_HEADERS, params=params)
        resp.raise_for_status()
        return resp.json()


# ─── Tool: get_firing_alerts ─────────────────────────────────────────────────
class GetFiringAlertsInput(BaseModel):
    folder: Optional[str] = None

@app.post("/tools/grafana_get_firing_alerts")
async def get_firing_alerts(body: GetFiringAlertsInput):
    if not GRAFANA_URL:
        return _mock_firing()
    params = {"state": "firing"}
    if body.folder:
        params["folderUID"] = body.folder
    return await _grafana_get("/api/v1/rules", params)


# ─── Tool: get_alert_rules ───────────────────────────────────────────────────
class GetAlertRulesInput(BaseModel):
    state: Optional[str] = None

@app.post("/tools/grafana_get_alert_rules")
async def get_alert_rules(body: GetAlertRulesInput):
    if not GRAFANA_URL:
        return _mock_rules()
    params = {}
    if body.state:
        params["state"] = body.state
    return await _grafana_get("/api/v1/rules", params)


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    if not GRAFANA_URL:
        return {"status": "ok", "mode": "mock"}
    try:
        await _grafana_get("/api/health")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


def _mock_firing():
    return {"data": {"groups": [{"name": "Production", "rules": [
        {"name": "[MOCK] High Memory Usage", "state": "firing",
         "labels": {"severity": "critical", "env": "prod"}},
    ]}]}}

def _mock_rules():
    return [{"name": "[MOCK] CPU Alert", "state": "normal"},
            {"name": "[MOCK] Memory Alert", "state": "firing"}]
