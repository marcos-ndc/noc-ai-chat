import json
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

from anthropic import AsyncAnthropic

from app.agent.prompt import get_system_prompt
from app.agent.session import session_manager
from app.models import (
    ChatMessage, MessageRole, SessionData,
    ToolName, WSEventType, WSOutbound,
)
from app.settings import settings

# ─── MCP Tool definitions ─────────────────────────────────────────────────────

MCP_TOOLS: list[dict] = [
    # Zabbix
    {
        "name": "zabbix_get_active_alerts",
        "description": "Busca alertas ativos no Zabbix. Filtre por severidade e grupo de hosts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["disaster", "high", "average", "warning", "info"]},
                "group": {"type": "string", "description": "Nome do grupo de hosts (opcional)"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "zabbix_get_active_problems",
        "description": "Zabbix 7.x: busca problemas ativos via problem.get. Retorna eventos com status, severidade, duração.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["information", "warning", "average", "high", "disaster"]},
                "group": {"type": "string"},
                "host": {"type": "string"},
                "limit": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "zabbix_get_host_status",
        "description": "Retorna status atual de um host específico no Zabbix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string"},
            },
            "required": ["hostname"],
        },
    },
    {
        "name": "zabbix_get_trigger_history",
        "description": "Histórico de triggers disparados para um host nas últimas N horas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string"},
                "hours": {"type": "integer", "default": 24},
                "severity": {"type": "string", "enum": ["disaster", "high", "average", "warning", "info"]},
            },
            "required": ["hostname"],
        },
    },
    {
        "name": "zabbix_get_item_latest",
        "description": "Busca o último valor de um item de monitoramento (CPU, memória, disco, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string"},
                "item_key": {"type": "string", "description": "Ex: system.cpu.util, vm.memory.size[available]"},
            },
            "required": ["hostname", "item_key"],
        },
    },
    {
        "name": "zabbix_get_host_groups",
        "description": "Lista todos os grupos de hosts cadastrados no Zabbix.",
        "input_schema": {"type": "object", "properties": {}},
    },
    # Datadog
    {
        "name": "datadog_get_active_monitors",
        "description": "Lista monitors ativos no Datadog com status de alerta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["Alert", "Warn", "No Data", "OK"], "default": "Alert"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "priority": {"type": "integer"},
            },
        },
    },
    {
        "name": "datadog_get_metrics",
        "description": "Busca métricas de um host ou serviço no Datadog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string"},
                "host": {"type": "string"},
                "from_minutes_ago": {"type": "integer", "default": 60},
            },
            "required": ["metric"],
        },
    },
    {
        "name": "datadog_get_logs",
        "description": "Busca logs recentes no Datadog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "default": "status:error"},
                "from_minutes_ago": {"type": "integer", "default": 30},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "datadog_get_incidents",
        "description": "Lista incidentes ativos no Datadog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["active", "stable", "resolved"], "default": "active"},
                "severity": {"type": "string", "enum": ["SEV-1", "SEV-2", "SEV-3", "SEV-4"]},
            },
        },
    },
    {
        "name": "datadog_get_hosts",
        "description": "Lista hosts monitorados no Datadog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string"},
                "count": {"type": "integer", "default": 30},
            },
        },
    },
    # Grafana
    {
        "name": "grafana_get_firing_alerts",
        "description": "Lista todos os alertas disparando no Grafana agora.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
            },
        },
    },
    {
        "name": "grafana_get_alert_rules",
        "description": "Lista regras de alerta configuradas no Grafana.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["firing", "pending", "normal", "error"]},
            },
        },
    },
    # ThousandEyes
    {
        "name": "thousandeyes_get_active_alerts",
        "description": "Lista alertas ativos no ThousandEyes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "alert_type": {"type": "string"},
            },
        },
    },
    {
        "name": "thousandeyes_get_test_results",
        "description": "Resultados recentes de um teste no ThousandEyes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_id": {"type": "string"},
                "window": {"type": "string", "default": "1h"},
            },
            "required": ["test_id"],
        },
    },
]

_TOOL_PREFIX_MAP: dict[str, ToolName] = {
    "zabbix":       ToolName.zabbix,
    "datadog":      ToolName.datadog,
    "grafana":      ToolName.grafana,
    "thousandeyes": ToolName.thousandeyes,
}


def _tool_to_noc_name(tool_name: str) -> Optional[ToolName]:
    for prefix, noc_name in _TOOL_PREFIX_MAP.items():
        if tool_name.startswith(prefix):
            return noc_name
    return None


class AgentOrchestrator:
    def __init__(self) -> None:
        # CR-2: AsyncAnthropic — never blocks the event loop
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._mcp_dispatcher: Optional["MCPDispatcher"] = None

    @property
    def mcp_dispatcher(self) -> "MCPDispatcher":
        if self._mcp_dispatcher is None:
            from app.agent.mcp_dispatcher import MCPDispatcher
            self._mcp_dispatcher = MCPDispatcher()
        return self._mcp_dispatcher

    async def process_message(
        self,
        user_message: str,
        session: SessionData,
    ) -> AsyncGenerator[WSOutbound, None]:
        """
        Yields WSOutbound events: tool_start → tool_end → agent_token → agent_done
        Uses real streaming (not fake chunking).
        """
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY não configurada. "
                "Adicione sua chave no arquivo .env e reinicie o stack."
            )

        session.messages.append(ChatMessage(role=MessageRole.user, content=user_message))
        await session_manager.save_session(session)

        system_prompt = get_system_prompt(session.user_profile)
        message_id = str(uuid.uuid4())[:8]

        # CR-5 fix: build_claude_messages now correctly maps agent→assistant
        claude_messages = session_manager.build_claude_messages(session)

        full_response = ""
        tools_used: set[ToolName] = set()

        # Agentic loop
        while True:
            # Non-streaming probe to detect tool calls
            probe = await self._client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=system_prompt,
                tools=MCP_TOOLS,  # type: ignore[arg-type]
                messages=claude_messages,
            )

            tool_calls = [
                {"id": b.id, "name": b.name, "input": b.input}
                for b in probe.content
                if b.type == "tool_use"
            ]

            # No tool calls → stream the final text response
            if not tool_calls:
                # CR-3: Real streaming — tokens arrive as Claude generates them
                async with self._client.messages.stream(
                    model=settings.claude_model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=claude_messages,
                ) as stream:
                    async for text in stream.text_stream:
                        full_response += text
                        yield WSOutbound(
                            type=WSEventType.agent_token,
                            messageId=message_id,
                            content=text,
                        )
                break

            # Execute tool calls
            claude_messages.append({
                "role": "assistant",
                "content": probe.content,  # type: ignore[arg-type]
            })

            tool_results = []
            for tc in tool_calls:
                noc_tool = _tool_to_noc_name(tc["name"])
                if noc_tool:
                    tools_used.add(noc_tool)
                    yield WSOutbound(type=WSEventType.tool_start, tool=noc_tool)

                result = await self.mcp_dispatcher.call(tc["name"], tc["input"])

                if noc_tool:
                    yield WSOutbound(type=WSEventType.tool_end, tool=noc_tool)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

            claude_messages.append({"role": "user", "content": tool_results})

        # Persist complete response
        if full_response:
            session.messages.append(
                ChatMessage(role=MessageRole.agent, content=full_response)
            )
            await session_manager.save_session(session)

        yield WSOutbound(type=WSEventType.agent_done, messageId=message_id)


orchestrator = AgentOrchestrator()
