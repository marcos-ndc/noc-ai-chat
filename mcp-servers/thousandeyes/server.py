"""
MCP Server — ThousandEyes
Integração com ThousandEyes API v7.
Suporta Bearer token (OAuth2) e Basic Auth (legado).
Fallback para mock quando THOUSANDEYES_TOKEN não configurado.
"""
import os
import time
import logging
from typing import Optional, Any
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

# ─── Configuração ─────────────────────────────────────────────────────────────

TE_TOKEN      = os.getenv("THOUSANDEYES_TOKEN", "")
TE_BASIC_USER = os.getenv("THOUSANDEYES_USER", "")   # legado Basic Auth
TE_BASIC_PASS = os.getenv("THOUSANDEYES_PASSWORD", "")
TE_AID        = os.getenv("THOUSANDEYES_AID", "")     # Account ID (opcional, multi-conta)
TE_TIMEOUT    = int(os.getenv("THOUSANDEYES_TIMEOUT", "15"))
TE_BASE       = "https://api.thousandeyes.com/v7"
SSL_VERIFY    = os.getenv("SSL_VERIFY", "false").lower() != "false"

MOCK_MODE = not bool(TE_TOKEN or (TE_BASIC_USER and TE_BASIC_PASS))

log = logging.getLogger("mcp-thousandeyes")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─── Cliente ThousandEyes ─────────────────────────────────────────────────────

class ThousandEyesClient:
    def __init__(self):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = None

        if TE_TOKEN:
            headers["Authorization"] = f"Bearer {TE_TOKEN}"
        elif TE_BASIC_USER:
            auth = (TE_BASIC_USER, TE_BASIC_PASS)

        self._client = httpx.AsyncClient(
            timeout=TE_TIMEOUT,
            verify=SSL_VERIFY,
            headers=headers,
            auth=auth,
        )
        self._aid_params = {"aid": TE_AID} if TE_AID else {}

    def _params(self, extra: Optional[dict] = None) -> dict:
        p = dict(self._aid_params)
        if extra:
            p.update(extra)
        return p

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        t0 = time.monotonic()
        resp = await self._client.get(
            f"{TE_BASE}{path}",
            params=self._params(params),
        )
        latency = (time.monotonic() - t0) * 1000
        log.info(f"te.get path={path} status={resp.status_code} latency={latency:.0f}ms")
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()


_te = ThousandEyesClient()

# ─── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MOCK_MODE:
        try:
            data = await _te.get("/status")
            log.info(f"thousandeyes.startup: conectado — {data}")
        except Exception as e:
            if "401" in str(e) or "403" in str(e):
                log.warning(f"thousandeyes.startup: credenciais inválidas — verifique THOUSANDEYES_TOKEN")
            elif "SSL" in str(e) or "certificate" in str(e).lower():
                log.warning(f"thousandeyes.startup: erro SSL corporativo — verifique SSL_VERIFY no .env")
            else:
                log.warning(f"thousandeyes.startup: não foi possível conectar: {e}")
    else:
        log.info("thousandeyes.startup: modo MOCK ativo (THOUSANDEYES_TOKEN não configurado)")
    yield
    await _te.close()


app = FastAPI(title="MCP ThousandEyes", version="2.0.0", lifespan=lifespan)


# ─── Tool: list_tests ─────────────────────────────────────────────────────────

@app.post("/tools/thousandeyes_list_tests")
async def list_tests(_: dict = {}):
    """Lista todos os testes configurados no ThousandEyes."""
    if MOCK_MODE:
        return _mock_tests()
    try:
        data = await _te.get("/tests")
        tests = data.get("tests", [])
        return {
            "count": len(tests),
            "tests": [
                {
                    "testId": t.get("testId"),
                    "testName": t.get("testName"),
                    "type": t.get("type"),
                    "url": t.get("url") or t.get("domain") or t.get("server"),
                    "interval": t.get("interval"),
                    "enabled": t.get("enabled"),
                    "agents": len(t.get("agents", [])),
                }
                for t in tests
            ],
        }
    except Exception as e:
        return {"error": str(e), "tool": "thousandeyes_list_tests"}


# ─── Tool: get_active_alerts ─────────────────────────────────────────────────

class GetActiveAlertsInput(BaseModel):
    alert_type: Optional[str] = None   # HTTP Server, Network, BGP, DNS, etc.
    test_name: Optional[str] = None

@app.post("/tools/thousandeyes_get_active_alerts")
async def get_active_alerts(body: GetActiveAlertsInput):
    """Lista alertas ativos no ThousandEyes."""
    if MOCK_MODE:
        return _mock_alerts()
    try:
        data = await _te.get("/alerts", {"window": "1h"})
        alerts = data.get("alerts", [])

        # Filtrar por tipo se solicitado
        if body.alert_type:
            alerts = [a for a in alerts if
                      body.alert_type.lower() in a.get("type", "").lower()]

        if body.test_name:
            alerts = [a for a in alerts if
                      body.test_name.lower() in a.get("testName", "").lower()]

        enriched = []
        for a in alerts:
            enriched.append({
                "alertId": a.get("alertId"),
                "alertType": a.get("type"),
                "testId": a.get("testId"),
                "testName": a.get("testName"),
                "severity": a.get("severity"),
                "active": a.get("active", 1),
                "dateStart": a.get("dateStart"),
                "agents": [
                    {"agentName": ag.get("agentName"), "location": ag.get("location")}
                    for ag in a.get("agents", [])
                ],
                "ruleName": a.get("ruleName"),
                "ruleExpression": a.get("ruleExpression"),
                "permalink": a.get("permalink"),
            })

        return {"count": len(enriched), "alerts": enriched}
    except Exception as e:
        return {"error": str(e), "tool": "thousandeyes_get_active_alerts"}


# ─── Tool: get_test_results ──────────────────────────────────────────────────

class GetTestResultsInput(BaseModel):
    test_id: str
    window: str = "1h"    # ex: 1h, 6h, 24h, 7d

@app.post("/tools/thousandeyes_get_test_results")
async def get_test_results(body: GetTestResultsInput):
    """Resultados recentes de um teste específico."""
    if MOCK_MODE:
        return _mock_results(body.test_id)
    try:
        # Busca detalhes do teste primeiro
        test_data = await _te.get(f"/tests/{body.test_id}")
        test = test_data.get("test", {})
        test_type = test.get("type", "")

        # Endpoints corretos da API ThousandEyes v7 por tipo de teste
        RESULT_PATHS = {
            "http-server":      f"/test-results/{body.test_id}/http-server",
            "page-load":        f"/test-results/{body.test_id}/page-load",
            "dns-server":       f"/test-results/{body.test_id}/dns-server",
            "dns-trace":        f"/test-results/{body.test_id}/dns-trace",
            "network":          f"/test-results/{body.test_id}/network/latency",
            "agent-to-server":  f"/test-results/{body.test_id}/network/latency",
            "agent-to-agent":   f"/test-results/{body.test_id}/network/latency",
            "bgp":              f"/test-results/{body.test_id}/bgp/routes",
            "ftp-server":       f"/test-results/{body.test_id}/ftp-server",
            "sip-server":       f"/test-results/{body.test_id}/sip-server",
            "voice":            f"/test-results/{body.test_id}/voice/metrics",
        }
        result_path = RESULT_PATHS.get(test_type, f"/test-results/{body.test_id}/http-server")

        results_data = await _te.get(result_path, {"window": body.window})
        results = results_data.get("results", [])

        # Métricas variam por tipo de teste
        is_network = test_type in ("network", "agent-to-server", "agent-to-agent")

        if results:
            if is_network:
                # Network tests: latency (avg/min/max), loss, jitter
                latency_vals = [r.get("avgLatency") or r.get("latency") for r in results
                                if r.get("avgLatency") or r.get("latency")]
                loss_vals = [r.get("loss") for r in results if r.get("loss") is not None]
                jitter_vals = [r.get("jitter") for r in results if r.get("jitter") is not None]
                avg_resp = sum(latency_vals) / len(latency_vals) if latency_vals else None
                avg_loss = sum(loss_vals) / len(loss_vals) if loss_vals else None
                avg_jitter = sum(jitter_vals) / len(jitter_vals) if jitter_vals else None
                avg_avail = None  # network tests don't have availability field
            else:
                avail_vals = [r.get("availability") for r in results if r.get("availability") is not None]
                resp_times = [r.get("responseTime") or r.get("connectTime") for r in results
                              if r.get("responseTime") or r.get("connectTime")]
                loss_vals = [r.get("loss") for r in results if r.get("loss") is not None]
                avg_avail = sum(avail_vals) / len(avail_vals) if avail_vals else None
                avg_resp = sum(resp_times) / len(resp_times) if resp_times else None
                avg_loss = sum(loss_vals) / len(loss_vals) if loss_vals else None
                avg_jitter = None
        else:
            avg_avail = avg_resp = avg_loss = avg_jitter = None

        aggregated: dict = {}
        if avg_avail is not None:
            aggregated["avg_availability"] = round(avg_avail, 2)
        if avg_resp is not None:
            key = "avg_latency_ms" if is_network else "avg_response_time_ms"
            aggregated[key] = round(avg_resp, 1)
        if avg_loss is not None:
            aggregated["avg_packet_loss_pct"] = round(avg_loss, 2)
        if avg_jitter is not None:
            aggregated["avg_jitter_ms"] = round(avg_jitter, 2)

        return {
            "testId": body.test_id,
            "testName": test.get("testName"),
            "testType": test_type,
            "isNetworkTest": is_network,
            "window": body.window,
            "result_count": len(results),
            "aggregated": aggregated,
            "results": results[:10],
        }
    except Exception as e:
        return {"error": str(e), "test_id": body.test_id, "tool": "thousandeyes_get_test_results"}


# ─── Tool: get_test_availability ─────────────────────────────────────────────

class GetTestAvailabilityInput(BaseModel):
    test_name: Optional[str] = None   # filtro por nome (parcial)
    window: str = "1h"
    threshold_pct: float = 99.0       # abaixo disso considera degradado

@app.post("/tools/thousandeyes_get_test_availability")
async def get_test_availability(body: GetTestAvailabilityInput):
    """
    Verifica disponibilidade de todos os testes (ou filtrado por nome).
    Identifica testes com disponibilidade abaixo do threshold.
    """
    if MOCK_MODE:
        return _mock_availability()
    try:
        # Lista testes
        tests_data = await _te.get("/tests")
        tests = tests_data.get("tests", [])

        if body.test_name:
            tests = [t for t in tests if body.test_name.lower() in t.get("testName", "").lower()]

        # Busca resultados de cada teste (limitado a 10 para não sobrecarregar)
        results = []
        degraded = []

        for test in tests[:15]:
            test_id = test.get("testId")
            test_type = test.get("type", "http-server")

            result_path = {
                "http-server": f"/test-results/{test_id}/http-server",
                "page-load": f"/test-results/{test_id}/page-load",
            }.get(test_type, f"/test-results/{test_id}/http-server")

            try:
                r_data = await _te.get(result_path, {"window": body.window})
                r_list = r_data.get("results", [])
                avail_vals = [r.get("availability") for r in r_list if r.get("availability") is not None]
                avg_avail = sum(avail_vals) / len(avail_vals) if avail_vals else None

                entry = {
                    "testId": test_id,
                    "testName": test.get("testName"),
                    "type": test_type,
                    "availability_pct": round(avg_avail, 2) if avg_avail is not None else "N/A",
                    "degraded": avg_avail is not None and avg_avail < body.threshold_pct,
                }
                results.append(entry)
                if entry["degraded"]:
                    degraded.append(entry)
            except Exception:
                results.append({
                    "testId": test_id,
                    "testName": test.get("testName"),
                    "type": test_type,
                    "availability_pct": "error",
                    "degraded": False,
                })

        return {
            "window": body.window,
            "threshold_pct": body.threshold_pct,
            "total_tests": len(results),
            "degraded_count": len(degraded),
            "degraded_tests": degraded,
            "all_tests": results,
        }
    except Exception as e:
        return {"error": str(e), "tool": "thousandeyes_get_test_availability"}


# ─── Tool: get_bgp_alerts ────────────────────────────────────────────────────

@app.post("/tools/thousandeyes_get_bgp_alerts")
async def get_bgp_alerts(_: dict = {}):
    """Lista alertas BGP ativos (route leaks, hijacks, path changes)."""
    if MOCK_MODE:
        return _mock_bgp()
    try:
        data = await _te.get("/alerts", {"window": "1h"})
        alerts = data.get("alerts", [])
        bgp_alerts = [a for a in alerts if "bgp" in a.get("type", "").lower()]
        return {"count": len(bgp_alerts), "bgp_alerts": bgp_alerts}
    except Exception as e:
        return {"error": str(e), "tool": "thousandeyes_get_bgp_alerts"}


# ─── Tool: get_agents ─────────────────────────────────────────────────────────

@app.post("/tools/thousandeyes_get_agents")
async def get_agents(_: dict = {}):
    """Lista agentes disponíveis (enterprise e cloud)."""
    if MOCK_MODE:
        return _mock_agents()
    try:
        data = await _te.get("/agents")
        agents = data.get("agents", [])
        return {
            "total": len(agents),
            "enterprise": [
                {"agentId": a.get("agentId"), "agentName": a.get("agentName"),
                 "location": a.get("location"), "status": a.get("agentState"),
                 "ipAddresses": a.get("ipAddresses", [])}
                for a in agents if a.get("agentType") == "ENTERPRISE"
            ],
            "cloud": [
                {"agentId": a.get("agentId"), "agentName": a.get("agentName"),
                 "location": a.get("location"), "countryId": a.get("countryId")}
                for a in agents if a.get("agentType") == "CLOUD"
            ],
        }
    except Exception as e:
        return {"error": str(e), "tool": "thousandeyes_get_agents"}


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    if MOCK_MODE:
        return {"status": "ok", "mode": "mock",
                "message": "Configure THOUSANDEYES_TOKEN para modo real"}
    try:
        t0 = time.monotonic()
        await _te.get("/status")
        latency = (time.monotonic() - t0) * 1000
        return {"status": "ok", "mode": "real", "latency_ms": round(latency, 1)}
    except Exception as e:
        err = str(e)
        if "401" in err or "403" in err:
            return {"status": "degraded", "error": "Credenciais inválidas", "mode": "real"}
        if "SSL" in err or "certificate" in err.lower():
            return {"status": "degraded", "error": "SSL corporativo — adicione SSL_VERIFY=false no .env", "mode": "real"}
        return {"status": "down", "error": err, "mode": "real"}


# ─── Mock data ────────────────────────────────────────────────────────────────

def _mock_tests():
    return {"count": 3, "tests": [
        {"testId": "101", "testName": "[MOCK] API Health Check", "type": "http-server",
         "url": "https://api.empresa.com/health", "interval": 60, "enabled": True, "agents": 3},
        {"testId": "102", "testName": "[MOCK] DNS Resolution", "type": "dns-server",
         "url": "empresa.com", "interval": 120, "enabled": True, "agents": 5},
        {"testId": "103", "testName": "[MOCK] Network Latency DC", "type": "agent-to-server",
         "url": "10.0.0.1", "interval": 60, "enabled": True, "agents": 2},
    ]}

def _mock_alerts():
    return {"count": 1, "alerts": [
        {"alertId": "4001", "alertType": "HTTP Server", "testId": "101",
         "testName": "[MOCK] API Health Check", "severity": "MAJOR",
         "active": 1, "dateStart": "2026-04-09T10:00:00Z",
         "agents": [{"agentName": "São Paulo, Brazil", "location": "São Paulo"}],
         "ruleName": "Availability < 90%", "permalink": ""},
    ]}

def _mock_results(test_id: str):
    return {
        "testId": test_id, "testName": "[MOCK] Test",
        "window": "1h", "result_count": 12,
        "aggregated": {"avg_availability": 98.5, "avg_response_time_ms": 245.0, "avg_packet_loss_pct": 0.0},
        "results": [{"availability": 98.5, "responseTime": 245, "loss": 0}],
    }

def _mock_availability():
    return {
        "window": "1h", "threshold_pct": 99.0, "total_tests": 3, "degraded_count": 1,
        "degraded_tests": [
            {"testId": "101", "testName": "[MOCK] API Health Check", "type": "http-server",
             "availability_pct": 97.5, "degraded": True}
        ],
        "all_tests": [
            {"testId": "101", "testName": "[MOCK] API Health Check", "type": "http-server", "availability_pct": 97.5, "degraded": True},
            {"testId": "102", "testName": "[MOCK] DNS Resolution", "type": "dns-server", "availability_pct": 100.0, "degraded": False},
            {"testId": "103", "testName": "[MOCK] Network Latency DC", "type": "agent-to-server", "availability_pct": 99.8, "degraded": False},
        ],
    }

def _mock_bgp():
    return {"count": 0, "bgp_alerts": [], "message": "[MOCK] Sem alertas BGP ativos"}

def _mock_agents():
    return {
        "total": 3,
        "enterprise": [
            {"agentId": "501", "agentName": "[MOCK] São Paulo Enterprise",
             "location": "São Paulo, Brazil", "status": "CONNECTED", "ipAddresses": ["10.0.0.10"]},
        ],
        "cloud": [
            {"agentId": "601", "agentName": "São Paulo, Brazil", "location": "São Paulo, Brazil", "countryId": "BR"},
            {"agentId": "602", "agentName": "New York, NY", "location": "New York", "countryId": "US"},
        ],
    }
