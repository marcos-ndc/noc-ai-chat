"""
MCP Server — ThousandEyes
Expõe tools para o agente consultar testes e alertas de rede.
"""
import os

# Proxy corporativo: SSL_VERIFY=false para ambientes com inspeção SSL
_SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() != "false"
from typing import Optional
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MCP ThousandEyes", version="1.0.0")

TE_TOKEN  = os.getenv("THOUSANDEYES_TOKEN", "")
TE_BASE   = "https://api.thousandeyes.com/v7"
_HEADERS  = {"Authorization": f"Bearer {TE_TOKEN}", "Content-Type": "application/json"}


async def _te_get(path: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=10.0, verify=_SSL_VERIFY) as client:
        resp = await client.get(f"{TE_BASE}{path}", headers=_HEADERS, params=params)
        resp.raise_for_status()
        return resp.json()


# ─── Tool: get_active_alerts ─────────────────────────────────────────────────
class GetActiveAlertsInput(BaseModel):
    alert_type: Optional[str] = None

@app.post("/tools/thousandeyes_get_active_alerts")
async def get_active_alerts(body: GetActiveAlertsInput):
    if not TE_TOKEN:
        return _mock_alerts()
    params = {}
    if body.alert_type:
        params["alertType"] = body.alert_type
    return await _te_get("/alerts", params)


# ─── Tool: get_test_results ──────────────────────────────────────────────────
class GetTestResultsInput(BaseModel):
    test_id: str
    window: str = "1h"

@app.post("/tools/thousandeyes_get_test_results")
async def get_test_results(body: GetTestResultsInput):
    if not TE_TOKEN:
        return _mock_results(body.test_id)
    return await _te_get(f"/tests/{body.test_id}/results", {"window": body.window})


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    if not TE_TOKEN:
        return {"status": "ok", "mode": "mock"}
    try:
        await _te_get("/status")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


def _mock_alerts():
    return {"alerts": [
        {"alertId": "4001", "alertType": "HTTP Server", "active": 1,
         "testName": "[MOCK] API Health Check", "severity": "MAJOR"},
    ]}

def _mock_results(test_id: str):
    return {"test": {"testId": test_id, "testName": "[MOCK] Test"},
            "results": [{"avgResponseTime": 450, "loss": 0, "availability": 98.5}]}
