import httpx
from typing import Any

from app.settings import settings


_MCP_URLS: dict[str, str] = {
    "zabbix":       settings.mcp_zabbix_url,
    "datadog":      settings.mcp_datadog_url,
    "grafana":      settings.mcp_grafana_url,
    "thousandeyes": settings.mcp_thousandeyes_url,
}


class MCPDispatcher:
    """Routes Claude tool calls to the appropriate MCP server."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=15.0)

    async def call(self, tool_name: str, tool_input: dict) -> Any:
        """
        Call a tool on the appropriate MCP server.
        tool_name format: "<service>_<action>" e.g. "zabbix_get_active_alerts"
        """
        prefix = tool_name.split("_")[0]
        base_url = _MCP_URLS.get(prefix)

        if not base_url:
            return {"error": f"Unknown tool service: {prefix}"}

        try:
            response = await self._client.post(
                f"{base_url}/tools/{tool_name}",
                json=tool_input,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            return {"error": f"Timeout calling {tool_name} — MCP server não respondeu em 15s"}
        except httpx.ConnectError:
            return {"error": f"MCP server {prefix} indisponível — verifique se o container está rodando"}
        except httpx.HTTPStatusError as e:
            return {"error": f"MCP server retornou erro {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"error": f"Erro inesperado em {tool_name}: {str(e)}"}

    async def health_check(self, service: str) -> dict:
        base_url = _MCP_URLS.get(service)
        if not base_url:
            return {"status": "unknown"}
        try:
            response = await self._client.get(f"{base_url}/health", timeout=3.0)
            return {"status": "ok" if response.status_code == 200 else "degraded"}
        except Exception:
            return {"status": "down"}
