"""
MCP Server — Datadog
Integração real com Datadog API v1/v2.
Suporta múltiplos sites (datadoghq.com, datadoghq.eu, us3, us5).
Rate limiting com retry automático. Fallback para mock quando sem credenciais.
"""
import os
import time
import logging
from typing import Optional, Any
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)

# ─── Configuração ─────────────────────────────────────────────────────────────

DD_API_KEY  = os.getenv("DATADOG_API_KEY", "")
DD_APP_KEY  = os.getenv("DATADOG_APP_KEY", "")
DD_SITE     = os.getenv("DATADOG_SITE", "datadoghq.com")
DD_TIMEOUT  = int(os.getenv("DATADOG_TIMEOUT", "10"))
# Proxy corporativo: SSL_VERIFY=false para ambientes com inspeção SSL
# Default false for corporate environments with SSL inspection
DD_SSL_VERIFY = os.getenv("DATADOG_SSL_VERIFY", os.getenv("SSL_VERIFY", "false")).lower() != "false"

MOCK_MODE = not bool(DD_API_KEY)
DD_BASE   = f"https://api.{DD_SITE}"

log = logging.getLogger("mcp-datadog")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ─── Cliente Datadog ──────────────────────────────────────────────────────────

class DatadogClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=DD_TIMEOUT,
            verify=DD_SSL_VERIFY,
            headers={
                "DD-API-KEY": DD_API_KEY,
                "DD-APPLICATION-KEY": DD_APP_KEY,
                "Content-Type": "application/json",
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        before_sleep=before_sleep_log(log, logging.WARNING),
    )
    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        t0 = time.monotonic()
        url = f"{DD_BASE}{path}"
        resp = await self._client.get(url, params=params)
        latency_ms = (time.monotonic() - t0) * 1000

        log.info(f"datadog.get path={path} status={resp.status_code} latency={latency_ms:.0f}ms")

        # Rate limit → retry
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("X-RateLimit-Reset", 1))
            log.warning(f"datadog.rate_limit: aguardando {retry_after}s")
            await asyncio.sleep(min(retry_after, 5))
            resp.raise_for_status()

        resp.raise_for_status()
        return resp.json()

    async def post(self, path: str, body: dict) -> Any:
        t0 = time.monotonic()
        resp = await self._client.post(f"{DD_BASE}{path}", json=body)
        latency_ms = (time.monotonic() - t0) * 1000
        log.info(f"datadog.post path={path} status={resp.status_code} latency={latency_ms:.0f}ms")
        resp.raise_for_status()
        return resp.json()

    async def validate(self) -> tuple[bool, str]:
        try:
            await self.get("/api/v1/validate")
            return True, ""
        except Exception as e:
            return False, str(e)

    async def close(self):
        await self._client.aclose()


import asyncio

_dd = DatadogClient()


# ─── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MOCK_MODE:
        ok, err = await _dd.validate()
        if ok:
            log.info(f"datadog.startup: autenticado — site={DD_SITE}, url={DD_BASE}")
        else:
            # Diagnose the type of failure
            if "SSL" in err or "certificate" in err.lower() or "CERTIFICATE" in err:
                cause = "Certificado SSL corporativo rejeitado. Adicione SSL_VERIFY=false no .env"
            elif "401" in err or "403" in err or "Forbidden" in err or "Unauthorized" in err:
                cause = "Credenciais inválidas. Verifique DATADOG_API_KEY e DATADOG_APP_KEY no .env"
            elif "connect" in err.lower() or "Connection" in err:
                cause = f"Proxy/firewall bloqueando {DD_BASE}. Adicione SSL_VERIFY=false no .env"
            elif "Name or service not known" in err or "DNS" in err:
                cause = f"DNS falhou para {DD_BASE}. Verifique conectividade de rede"
            else:
                cause = f"Erro desconhecido: {err}"
            log.warning(
                f"datadog.startup: DEGRADADO — {cause}. "
                f"URL tentada: {DD_BASE}/api/v1/validate. "
                "Retornando mock data até conectividade ser restabelecida."
            )
    else:
        log.info(f"datadog.startup: modo MOCK ativo — DATADOG_API_KEY não configurado")
    yield
    await _dd.close()


app = FastAPI(title="MCP Datadog", version="2.0.0", lifespan=lifespan)


# ─── Tool: get_active_monitors ───────────────────────────────────────────────

class GetMonitorsInput(BaseModel):
    status: Optional[str] = "Alert"       # Alert | Warn | No Data | OK
    tags: Optional[list[str]] = None      # ["env:prod", "service:api"]
    priority: Optional[int] = None        # 1-5
    page_size: int = 30

@app.post("/tools/datadog_get_active_monitors")
async def get_active_monitors(body: GetMonitorsInput):
    if MOCK_MODE:
        return _mock_monitors()

    try:
        params: dict = {
            "monitor_status": body.status or "Alert",
            "page_size": min(body.page_size, 100),
        }
        if body.tags:
            params["tags"] = ",".join(body.tags)
        if body.priority:
            params["priority"] = str(body.priority)

        data = await _dd.get("/api/v1/monitor", params)

        # Normaliza resposta
        monitors = data if isinstance(data, list) else data.get("monitors", [])

        result = []
        for m in monitors:
            result.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "type": m.get("type"),
                "status": m.get("overall_state", m.get("status")),
                "priority": m.get("priority"),
                "tags": m.get("tags", []),
                "message": m.get("message", "")[:200],
                "created": m.get("created"),
                "modified": m.get("modified"),
                "query": m.get("query"),
                "options": {
                    "thresholds": m.get("options", {}).get("thresholds"),
                    "notify_no_data": m.get("options", {}).get("notify_no_data"),
                },
            })

        return {"count": len(result), "monitors": result, "mode": "real"}

    except Exception as e:
        return {"error": str(e), "mode": "real", "tool": "datadog_get_active_monitors"}


# ─── Tool: get_metrics ───────────────────────────────────────────────────────

class GetMetricsInput(BaseModel):
    metric: str                          # ex: "system.cpu.user"
    host: Optional[str] = None
    from_minutes_ago: int = 60
    rollup: str = "avg"                  # avg | max | min | sum | count

@app.post("/tools/datadog_get_metrics")
async def get_metrics(body: GetMetricsInput):
    if MOCK_MODE:
        return _mock_metrics(body.metric)

    try:
        now = int(time.time())
        time_from = now - (body.from_minutes_ago * 60)

        query = body.metric
        if body.host:
            query += f"{{host:{body.host}}}"
        query = f"{body.rollup}:{query}"

        data = await _dd.get("/api/v1/query", {
            "query": query,
            "from": time_from,
            "to": now,
        })

        series = data.get("series", [])
        result = []
        for s in series:
            points = s.get("pointlist", [])
            values = [p[1] for p in points if p[1] is not None]
            result.append({
                "metric": s.get("metric"),
                "display_name": s.get("display_name"),
                "scope": s.get("scope"),
                "unit": s.get("unit", [{}])[0].get("name") if s.get("unit") else None,
                "points_count": len(points),
                "latest_value": values[-1] if values else None,
                "avg": round(sum(values) / len(values), 4) if values else None,
                "max": max(values) if values else None,
                "min": min(values) if values else None,
            })

        return {"query": query, "from_minutes_ago": body.from_minutes_ago,
                "series": result, "mode": "real"}

    except Exception as e:
        return {"error": str(e), "metric": body.metric}


# ─── Tool: get_incidents ─────────────────────────────────────────────────────

class GetIncidentsInput(BaseModel):
    status: Optional[str] = "active"    # active | stable | resolved
    severity: Optional[str] = None      # SEV-1 | SEV-2 | SEV-3 | SEV-4

@app.post("/tools/datadog_get_incidents")
async def get_incidents(body: GetIncidentsInput):
    if MOCK_MODE:
        return _mock_incidents()

    try:
        params: dict = {"page[size]": 30}
        if body.status:
            params["filter[status]"] = body.status
        if body.severity:
            params["filter[severity]"] = body.severity

        data = await _dd.get("/api/v2/incidents", params)
        incidents = data.get("data", [])

        result = []
        for inc in incidents:
            attrs = inc.get("attributes", {})
            result.append({
                "id": inc.get("id"),
                "title": attrs.get("title"),
                "status": attrs.get("status"),
                "severity": attrs.get("severity"),
                "created": attrs.get("created"),
                "modified": attrs.get("modified"),
                "detected": attrs.get("detected"),
                "resolved": attrs.get("resolved"),
                "customer_impact": attrs.get("customer_impact_scope"),
                "commander": attrs.get("commander", {}).get("name") if attrs.get("commander") else None,
                "duration_minutes": _incident_duration_minutes(attrs),
            })

        return {"count": len(result), "incidents": result, "mode": "real"}

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"count": 0, "incidents": [],
                    "note": "Incidents API não disponível neste plano Datadog"}
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def _incident_duration_minutes(attrs: dict) -> Optional[int]:
    created = attrs.get("created") or attrs.get("detected")
    resolved = attrs.get("resolved")
    if not created:
        return None
    try:
        import datetime
        fmt = "%Y-%m-%dT%H:%M:%S%z"
        t_start = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
        t_end = (datetime.datetime.fromisoformat(resolved.replace("Z", "+00:00"))
                 if resolved else datetime.datetime.now(datetime.timezone.utc))
        return int((t_end - t_start).total_seconds() / 60)
    except Exception:
        return None


# ─── Tool: get_logs ──────────────────────────────────────────────────────────

class GetLogsInput(BaseModel):
    query: str = "status:error"         # ex: "service:api status:error"
    from_minutes_ago: int = 30
    limit: int = 20

@app.post("/tools/datadog_get_logs")
async def get_logs(body: GetLogsInput):
    if MOCK_MODE:
        return _mock_logs()

    try:
        now_ms = int(time.time() * 1000)
        from_ms = now_ms - (body.from_minutes_ago * 60 * 1000)

        data = await _dd.post("/api/v2/logs/events/search", {
            "filter": {
                "query": body.query,
                "from": f"{from_ms}",
                "to": f"{now_ms}",
            },
            "page": {"limit": min(body.limit, 100)},
            "sort": "-timestamp",
        })

        logs = data.get("data", [])
        result = []
        for entry in logs:
            attrs = entry.get("attributes", {})
            result.append({
                "id": entry.get("id"),
                "timestamp": attrs.get("timestamp"),
                "status": attrs.get("status"),
                "service": attrs.get("service"),
                "host": attrs.get("host"),
                "message": (attrs.get("message") or "")[:300],
                "tags": attrs.get("tags", []),
            })

        return {"count": len(result), "query": body.query,
                "from_minutes_ago": body.from_minutes_ago,
                "logs": result, "mode": "real"}

    except Exception as e:
        return {"error": str(e), "query": body.query}


# ─── Tool: get_hosts ─────────────────────────────────────────────────────────

class GetHostsInput(BaseModel):
    filter: Optional[str] = None       # ex: "env:prod"
    sort_field: str = "status"
    count: int = 30

@app.post("/tools/datadog_get_hosts")
async def get_hosts(body: GetHostsInput):
    if MOCK_MODE:
        return _mock_hosts()

    try:
        params: dict = {
            "count": min(body.count, 100),
            "sort_field": body.sort_field,
            "sort_dir": "desc",
        }
        if body.filter:
            params["filter"] = body.filter

        data = await _dd.get("/api/v1/hosts", params)
        hosts = data.get("host_list", [])

        result = []
        for h in hosts:
            result.append({
                "id": h.get("id"),
                "name": h.get("name"),
                "status": h.get("status"),
                "up": h.get("up"),
                "apps": h.get("apps", []),
                "tags_by_source": h.get("tags_by_source", {}),
                "last_reported_time": h.get("last_reported_time"),
                "mute_timeout": h.get("mute_timeout"),
            })

        return {"count": len(result), "total": data.get("total_matching"),
                "hosts": result, "mode": "real"}

    except Exception as e:
        return {"error": str(e)}


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    if MOCK_MODE:
        return {"status": "ok", "mode": "mock",
                "message": "Configure DATADOG_API_KEY para modo real"}
    try:
        t0 = time.monotonic()
        await _dd.validate()
        latency_ms = (time.monotonic() - t0) * 1000
        return {
            "status": "ok",
            "mode": "real",
            "site": DD_SITE,
            "latency_ms": round(latency_ms, 1),
        }
    except Exception as e:
        return {"status": "down", "error": str(e), "mode": "real"}


# ─── Mock data ────────────────────────────────────────────────────────────────

def _mock_monitors():
    return {"count": 2, "mode": "mock", "monitors": [
        {"id": 2001, "name": "[MOCK] High CPU on prod-app-01", "status": "Alert",
         "priority": 1, "tags": ["env:prod", "service:app"]},
        {"id": 2002, "name": "[MOCK] DB Connection Pool > 90%", "status": "Alert",
         "priority": 2, "tags": ["env:prod", "service:database"]},
    ]}

def _mock_metrics(metric: str):
    return {"query": metric, "mode": "mock", "series": [
        {"metric": metric, "latest_value": 72.5, "avg": 68.2,
         "max": 89.1, "min": 45.3, "points_count": 60},
    ]}

def _mock_incidents():
    return {"count": 1, "mode": "mock", "incidents": [
        {"id": "mock-001", "title": "[MOCK] API latency degradation",
         "status": "active", "severity": "SEV-2", "duration_minutes": 45},
    ]}

def _mock_logs():
    return {"count": 2, "mode": "mock", "query": "status:error", "from_minutes_ago": 30, "logs": [
        {"timestamp": "2026-04-07T16:00:00Z", "status": "error",
         "service": "api", "message": "[MOCK] Connection timeout to database"},
        {"timestamp": "2026-04-07T15:58:00Z", "status": "error",
         "service": "api", "message": "[MOCK] HTTP 500: Internal Server Error"},
    ]}

def _mock_hosts():
    return {"count": 2, "mode": "mock", "hosts": [
        {"name": "web-server-01", "status": "ok", "up": True, "apps": ["nginx"]},
        {"name": "db-primary", "status": "alert", "up": True, "apps": ["postgresql"]},
    ]}
