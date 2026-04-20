import json
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

import structlog
from anthropic import AsyncAnthropic

log = structlog.get_logger()

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
    {"name": "zabbix_list_organizations",
     "description": "Lista todos os clientes/organizações monitorados no Zabbix via tag 'Organization'. Use quando o usuário perguntar quais clientes estão monitorados.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "zabbix_get_organization_summary",
     "description": "Resumo completo de um cliente: hosts, disponibilidade, problemas ativos por severidade. Use para visão geral de um cliente específico.",
     "input_schema": {"type": "object", "properties": {
         "organization": {"type": "string", "description": "Valor da tag Organization (nome do cliente)"}},
         "required": ["organization"]}},
    {"name": "zabbix_get_active_alerts",
     "description": "Busca alertas ativos no Zabbix. Filtre por organização (cliente), severidade, grupo ou host.",
     "input_schema": {"type": "object", "properties": {
         "organization": {"type": "string", "description": "Tag Organization do cliente"},
         "severity": {"type": "string", "enum": ["disaster", "high", "average", "warning", "information"]},
         "group": {"type": "string"}, "host": {"type": "string"},
         "limit": {"type": "integer", "default": 30}}}},
    {"name": "zabbix_get_active_problems",
     "description": "Zabbix 7.x: problemas ativos via problem.get. Suporta filtro por organização/cliente.",
     "input_schema": {"type": "object", "properties": {
         "organization": {"type": "string", "description": "Tag Organization do cliente"},
         "severity": {"type": "string", "enum": ["information", "warning", "average", "high", "disaster"]},
         "group": {"type": "string"}, "host": {"type": "string"}, "limit": {"type": "integer", "default": 30}}}},
    {"name": "zabbix_get_host_status",
     "description": "Retorna status atual de um host específico no Zabbix.",
     "input_schema": {"type": "object", "properties": {"hostname": {"type": "string"}}, "required": ["hostname"]}},
    {"name": "zabbix_get_trigger_history",
     "description": "Histórico de triggers disparados para um host nas últimas N horas.",
     "input_schema": {"type": "object", "properties": {
         "hostname": {"type": "string"}, "hours": {"type": "integer", "default": 24},
         "severity": {"type": "string", "enum": ["disaster", "high", "average", "warning", "info"]}},
         "required": ["hostname"]}},
    {"name": "zabbix_get_item_latest",
     "description": "Busca o último valor de um item de monitoramento (CPU, memória, disco, etc.).",
     "input_schema": {"type": "object", "properties": {
         "hostname": {"type": "string"},
         "item_key": {"type": "string", "description": "Ex: system.cpu.util, vm.memory.size[available]"}},
         "required": ["hostname", "item_key"]}},
    {"name": "zabbix_get_host_groups",
     "description": "Lista todos os grupos de hosts cadastrados no Zabbix.",
     "input_schema": {"type": "object", "properties": {}}},
    # Datadog
    {"name": "datadog_get_active_monitors",
     "description": "Lista monitors ativos no Datadog com status de alerta.",
     "input_schema": {"type": "object", "properties": {
         "status": {"type": "string", "enum": ["Alert", "Warn", "No Data", "OK"], "default": "Alert"},
         "tags": {"type": "array", "items": {"type": "string"}}, "priority": {"type": "integer"}}}},
    {"name": "datadog_get_metrics",
     "description": "Busca métricas de um host ou serviço no Datadog.",
     "input_schema": {"type": "object", "properties": {
         "metric": {"type": "string"}, "host": {"type": "string"},
         "from_minutes_ago": {"type": "integer", "default": 60}}, "required": ["metric"]}},
    {"name": "datadog_get_logs",
     "description": "Busca logs recentes no Datadog.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "default": "status:error"},
         "from_minutes_ago": {"type": "integer", "default": 30}, "limit": {"type": "integer", "default": 20}}}},
    {"name": "datadog_get_incidents",
     "description": "Lista incidentes ativos no Datadog.",
     "input_schema": {"type": "object", "properties": {
         "status": {"type": "string", "enum": ["active", "stable", "resolved"], "default": "active"},
         "severity": {"type": "string", "enum": ["SEV-1", "SEV-2", "SEV-3", "SEV-4"]}}}},
    {"name": "datadog_get_hosts",
     "description": "Lista hosts monitorados no Datadog.",
     "input_schema": {"type": "object", "properties": {
         "filter": {"type": "string"}, "count": {"type": "integer", "default": 30}}}},
    # Grafana
    {"name": "grafana_get_firing_alerts",
     "description": "Lista todos os alertas disparando no Grafana agora.",
     "input_schema": {"type": "object", "properties": {"folder": {"type": "string"}}}},
    {"name": "grafana_get_alert_rules",
     "description": "Lista regras de alerta configuradas no Grafana.",
     "input_schema": {"type": "object", "properties": {
         "state": {"type": "string", "enum": ["firing", "pending", "normal", "error"]}}}},
    # ThousandEyes
    # ThousandEyes
    {"name": "thousandeyes_list_tests",
     "description": "Lista todos os testes configurados no ThousandEyes (HTTP, DNS, Network, BGP, etc.).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "thousandeyes_get_active_alerts",
     "description": "Lista alertas ativos no ThousandEyes. Filtre por tipo (HTTP Server, Network, BGP, DNS).",
     "input_schema": {"type": "object", "properties": {
         "alert_type": {"type": "string", "description": "Tipo: HTTP Server, Network, BGP, DNS"},
         "test_name": {"type": "string", "description": "Filtro parcial por nome do teste"}}}},
    {"name": "thousandeyes_get_test_results",
     "description": "Resultados e métricas de um teste específico (availability, response time, packet loss).",
     "input_schema": {"type": "object", "properties": {
         "test_id": {"type": "string"}, "window": {"type": "string", "default": "1h",
         "description": "Janela: 1h, 6h, 24h, 7d"}}, "required": ["test_id"]}},
    {"name": "thousandeyes_get_test_availability",
     "description": "Verifica disponibilidade de todos os testes. Identifica testes degradados abaixo de um threshold.",
     "input_schema": {"type": "object", "properties": {
         "test_name": {"type": "string", "description": "Filtro parcial por nome"},
         "window": {"type": "string", "default": "1h"},
         "threshold_pct": {"type": "number", "default": 99.0, "description": "% mínimo de disponibilidade"}}}},
    {"name": "thousandeyes_get_bgp_alerts",
     "description": "Lista alertas BGP ativos (route leaks, hijacks, mudanças de path).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "thousandeyes_get_agents",
     "description": "Lista agentes ThousandEyes disponíveis (enterprise e cloud) com localização e status.",
     "input_schema": {"type": "object", "properties": {}}},
]

_TOOL_PREFIX_MAP: dict[str, ToolName] = {
    "zabbix": ToolName.zabbix, "datadog": ToolName.datadog,
    "grafana": ToolName.grafana, "thousandeyes": ToolName.thousandeyes,
}


def _tool_to_noc_name(tool_name: str) -> Optional[ToolName]:
    for prefix, noc_name in _TOOL_PREFIX_MAP.items():
        if tool_name.startswith(prefix):
            return noc_name
    return None


class AgentOrchestrator:
    def __init__(self) -> None:
        # Client built per-request via process_message to support runtime config changes
        self._mcp_dispatcher: Optional["MCPDispatcher"] = None

    def _build_client(self, api_key: str, base_url: Optional[str] = None) -> AsyncAnthropic:
        import httpx, os
        ca_cert    = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
        is_openrouter = bool(base_url and "openrouter" in base_url)
        # SSL verify:
        # - OpenRouter: default FALSE (external service, corporate proxies block it)
        # - Anthropic: reads ANTHROPIC_SSL_VERIFY (default depends on env)
        if is_openrouter:
            ssl_verify = os.environ.get("OPENROUTER_SSL_VERIFY",
                         os.environ.get("ANTHROPIC_SSL_VERIFY", "false")).lower() != "false"
        else:
            ssl_verify = os.environ.get("ANTHROPIC_SSL_VERIFY", "true").lower() != "false"

        # OpenRouter pode ser mais lento (roteamento externo) — timeout maior
        timeout = httpx.Timeout(120.0, connect=30.0) if is_openrouter else httpx.Timeout(60.0, connect=15.0)

        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        if ca_cert:
            kwargs["http_client"] = httpx.AsyncClient(verify=ca_cert, timeout=timeout)
        elif not ssl_verify:
            import warnings
            warnings.warn("SSL verification disabled for Anthropic/OpenRouter API")
            kwargs["http_client"] = httpx.AsyncClient(verify=False, timeout=timeout)
        else:
            kwargs["http_client"] = httpx.AsyncClient(timeout=timeout)

        return AsyncAnthropic(**kwargs)
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
        voice_mode: bool = False,
    ) -> AsyncGenerator[WSOutbound, None]:
        """
        Yields: tool_start → tool_end → agent_token (real streaming) → agent_done

        Flow per iteration:
          1. Stream call — yields text tokens in real time
          2. If stream ends with tool_use: execute tools, add results, loop
          3. If stream ends with end_turn: done
        This is ONE API call per iteration (not two), with real streaming.
        """
        # Load runtime AI config (provider + model + api_key from admin panel)
        from app.agent.ai_config import ai_config_store
        from app.models import AIProvider
        cfg = await ai_config_store.get()

        api_key  = cfg.api_key or settings.anthropic_api_key
        base_url = cfg.openrouter_base_url if cfg.provider == AIProvider.openrouter else None

        if not api_key:
            raise ValueError(
                "API key nao configurada. "
                "Configure em /admin ou adicione ANTHROPIC_API_KEY no .env."
            )

        session.messages.append(ChatMessage(role=MessageRole.user, content=user_message))
        await session_manager.save_session(session)

        system_prompt = get_system_prompt(session.user_profile, voice_mode=voice_mode)
        message_id = str(uuid.uuid4())[:8]

        claude_messages = session_manager.build_claude_messages(session)

        full_response = ""

        # ── Agentic loop (one stream call per iteration) ──────────────────────
        # Build the right client per provider
        from app.agent.llm_client import (
            build_anthropic_client, build_openrouter_client,
            stream_anthropic, stream_openrouter,
        )
        from app.models import AIProvider as _AIProvider
        if cfg.provider == _AIProvider.openrouter:
            llm = build_openrouter_client(
                api_key, cfg.openrouter_base_url,
                site_name=cfg.site_name, site_url=cfg.site_url,
            )
            stream_fn = stream_openrouter
        else:
            llm = build_anthropic_client(api_key)
            stream_fn = stream_anthropic

        while True:
            streamed_text = ""
            tool_calls: list[dict] = []

            async for event_type, event_data in stream_fn(
                llm, cfg.model, cfg.max_tokens, 1.0,
                system_prompt, claude_messages, MCP_TOOLS,
            ):
                if event_type == "text":
                    text = event_data
                    streamed_text += text
                    full_response += text
                    yield WSOutbound(
                        type=WSEventType.agent_token,
                        messageId=message_id,
                        content=text,
                    )
                elif event_type == "final":
                    final_msg = event_data

            tool_calls = [
                {"id": b.id, "name": b.name, "input": b.input}
                for b in final_msg.content
                if b.type == "tool_use"
            ]

            log.info("orchestrator.iteration",
                stop_reason=final_msg.stop_reason,
                tool_calls=[tc["name"] for tc in tool_calls],
                streamed_chars=len(streamed_text),
            )

            # No tool calls → done
            if not tool_calls:
                break

            # Add assistant message with tool use to history
            claude_messages.append({
                "role": "assistant",
                "content": final_msg.content,  # type: ignore[arg-type]
            })

            # Execute tool calls
            tool_results = []
            for tc in tool_calls:
                noc_tool = _tool_to_noc_name(tc["name"])
                if noc_tool:
                    yield WSOutbound(type=WSEventType.tool_start, tool=noc_tool)

                log.info("orchestrator.tool_call", tool=tc["name"], input=tc["input"])
                result = await self.mcp_dispatcher.call(tc["name"], tc["input"])
                has_error = isinstance(result, dict) and "error" in result
                log.info("orchestrator.tool_result",
                    tool=tc["name"],
                    has_error=has_error,
                    error_detail=result.get("error") if has_error else None,
                    error_type=result.get("error_type") if has_error else None,
                    result_preview=str(result)[:200] if not has_error else None,
                )

                if noc_tool:
                    yield WSOutbound(type=WSEventType.tool_end, tool=noc_tool)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

            claude_messages.append({"role": "user", "content": tool_results})
            # loop → next stream call includes tool results

        # ── Persist complete response ─────────────────────────────────────────
        if full_response:
            session.messages.append(
                ChatMessage(role=MessageRole.agent, content=full_response)
            )
            await session_manager.save_session(session)

        yield WSOutbound(type=WSEventType.agent_done, messageId=message_id)


orchestrator = AgentOrchestrator()
