import json
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

import anthropic

from app.agent.prompt import get_system_prompt
from app.agent.session import session_manager
from app.models import (
    ChatMessage, MessageRole, SessionData,
    ToolName, UserOut, UserProfile,
    WSEventType, WSOutbound,
)
from app.settings import settings

# ─── MCP Tool definitions per tool ───────────────────────────────────────────

MCP_TOOLS: list[dict] = [
    # Zabbix
    {
        "name": "zabbix_get_active_alerts",
        "description": "Busca alertas ativos no Zabbix. Filtre por severidade e grupo de hosts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["disaster", "high", "average", "warning", "info"], "description": "Severidade mínima"},
                "group": {"type": "string", "description": "Nome do grupo de hosts (opcional)"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "zabbix_get_host_status",
        "description": "Retorna status atual de um host específico no Zabbix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string", "description": "Nome ou IP do host"},
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
    # Datadog
    {
        "name": "datadog_get_active_monitors",
        "description": "Lista monitors ativos no Datadog com status de alerta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["Alert", "Warn", "No Data", "OK"], "default": "Alert"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags para filtrar (ex: ['env:prod'])"},
                "priority": {"type": "integer", "description": "Prioridade 1-5"},
            },
        },
    },
    {
        "name": "zabbix_get_active_problems",
        "description": "Zabbix 7.x: busca problemas ativos via problem.get (mais preciso que trigger.get). Retorna eventos com status, severidade, duração e se está reconhecido.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["information", "warning", "average", "high", "disaster"], "description": "Severidade mínima"},
                "group": {"type": "string", "description": "Nome do grupo de hosts"},
                "host": {"type": "string", "description": "Hostname específico"},
                "limit": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "zabbix_get_item_latest",
        "description": "Busca o último valor de um item de monitoramento no Zabbix (CPU, memória, disco, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string"},
                "item_key": {"type": "string", "description": "Chave do item. Ex: system.cpu.util, vm.memory.size[available], vfs.fs.size[/,pfree]"},
            },
            "required": ["hostname", "item_key"],
        },
    },
    {
        "name": "zabbix_get_host_groups",
        "description": "Lista todos os grupos de hosts cadastrados no Zabbix.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "datadog_get_logs",
        "description": "Busca logs recentes no Datadog com filtro por query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query Datadog. Ex: 'service:api status:error', 'host:web-01 @http.status_code:500'", "default": "status:error"},
                "from_minutes_ago": {"type": "integer", "default": 30},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "datadog_get_hosts",
        "description": "Lista hosts monitorados no Datadog com status e apps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Filtro. Ex: 'env:prod', 'role:database'"},
                "count": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "datadog_get_metrics",
        "description": "Busca métricas de um host ou serviço no Datadog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Nome da métrica (ex: system.cpu.user)"},
                "host": {"type": "string"},
                "from_minutes_ago": {"type": "integer", "default": 60},
            },
            "required": ["metric"],
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
    # Grafana
    {
        "name": "grafana_get_firing_alerts",
        "description": "Lista todos os alertas disparando no Grafana no momento.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Pasta de regras de alerta (opcional)"},
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
                "alert_type": {"type": "string", "description": "Tipo de alerta (ex: HTTP Server, Network, BGP)"},
            },
        },
    },
    {
        "name": "thousandeyes_get_test_results",
        "description": "Resultados recentes de um teste específico no ThousandEyes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_id": {"type": "string", "description": "ID do teste"},
                "window": {"type": "string", "default": "1h", "description": "Janela de tempo (ex: 1h, 6h, 24h)"},
            },
            "required": ["test_id"],
        },
    },
]

# Map tool name prefix to ToolName enum
_TOOL_PREFIX_MAP: dict[str, ToolName] = {
    "zabbix": ToolName.zabbix,
    "datadog": ToolName.datadog,
    "grafana": ToolName.grafana,
    "thousandeyes": ToolName.thousandeyes,
}


def _tool_to_noc_name(tool_name: str) -> Optional[ToolName]:
    for prefix, noc_name in _TOOL_PREFIX_MAP.items():
        if tool_name.startswith(prefix):
            return noc_name
    return None


class AgentOrchestrator:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
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
        Process a user message and yield WSOutbound events:
        tool_start → tool_end → agent_token (stream) → agent_done
        """
        from app.models import ChatMessage, MessageRole
        # Append user message to session
        session.messages.append(ChatMessage(role=MessageRole.user, content=user_message))
        await session_manager.save_session(session)

        system_prompt = get_system_prompt(session.user_profile)
        message_id = str(uuid.uuid4())[:8]

        # Build messages for Claude
        claude_messages = [
            {
                "role": "user" if m.role == MessageRole.user else "assistant",
                "content": m.content,
            }
            for m in session.messages
        ]

        # Agentic loop: Claude may call tools multiple times
        full_response = ""
        tools_used: set[ToolName] = set()

        while True:
            response = self._client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=system_prompt,
                tools=MCP_TOOLS,  # type: ignore[arg-type]
                messages=claude_messages,
            )

            # Process response content blocks
            text_parts: list[str] = []
            tool_calls: list[dict] = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            # Stream any text content token by token
            if text_parts:
                combined = "".join(text_parts)
                # Simulate streaming by yielding chunks
                chunk_size = 4
                for i in range(0, len(combined), chunk_size):
                    chunk = combined[i:i + chunk_size]
                    full_response += chunk
                    yield WSOutbound(
                        type=WSEventType.agent_token,
                        messageId=message_id,
                        content=chunk,
                    )

            # If no tool calls, we're done
            if not tool_calls or response.stop_reason == "end_turn":
                break

            # Add assistant message with tool calls to history
            claude_messages.append({
                "role": "assistant",
                "content": response.content,  # type: ignore[arg-type]
            })

            # Execute tool calls
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
                    "content": json.dumps(result),
                })

            # Add tool results to conversation
            claude_messages.append({"role": "user", "content": tool_results})

        # Save agent response to session
        if full_response:
            session.messages.append(
                ChatMessage(role=MessageRole.agent, content=full_response)
            )
            await session_manager.save_session(session)

        yield WSOutbound(
            type=WSEventType.agent_done,
            messageId=message_id,
        )


orchestrator = AgentOrchestrator()
