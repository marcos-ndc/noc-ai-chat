import time
from fastapi import APIRouter
from app.agent.mcp_dispatcher import MCPDispatcher
from app.agent.session import session_manager
from app.models import HealthResponse, ServiceStatus

router = APIRouter(tags=["health"])
_dispatcher = MCPDispatcher()


@router.get("/health", response_model=HealthResponse)
async def health():
    services: list[ServiceStatus] = []

    # Redis
    try:
        t0 = time.monotonic()
        await session_manager.redis.ping()
        latency = (time.monotonic() - t0) * 1000
        services.append(ServiceStatus(name="redis", status="ok", latency_ms=round(latency, 1)))
    except Exception:
        services.append(ServiceStatus(name="redis", status="down"))

    # MCP servers
    for svc in ["zabbix", "datadog", "grafana", "thousandeyes", "catalyst"]:
        result = await _dispatcher.health_check(svc)
        services.append(ServiceStatus(name=f"mcp-{svc}", status=result["status"]))

    overall = "ok" if all(s.status == "ok" for s in services if s.name == "redis") else "degraded"

    return HealthResponse(status=overall, services=services)
