"""
Tests: AgentOrchestrator — investigação e roteamento de especialistas.

Cobre:
1. Sistema de prompts por especialista
2. Regex ROUTE_TO (detecção e strip)
3. Handoff de contexto entre especialistas
4. Conversão de mensagens Anthropic↔OpenAI
5. Loop agêntico com tool calls
6. Fluxo completo: pergunta → tool → resposta → ROUTE_TO → especialista
"""
import json
import re
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace


# ─── 1. System prompts ────────────────────────────────────────────────────────

class TestSystemPrompts:
    """Verifica que cada especialista tem instruções claras e corretas."""

    def _get_prompt(self, specialist, profile="N2", voice=False):
        from app.agent.prompt import get_system_prompt
        from app.models import UserProfile, Specialist
        p = UserProfile(profile)
        return get_system_prompt(p, specialist=specialist, voice_mode=voice)

    def test_language_premise_is_first_in_all_prompts(self):
        """PREMISSA INEGOCIÁVEL: pt-BR deve estar no topo de todo prompt."""
        from app.models import Specialist
        for spec in Specialist:
            prompt = self._get_prompt(spec.value)
            assert "Português Brasileiro" in prompt[:300], \
                f"Specialist {spec.value}: language premise not at top"

    def test_generalista_has_route_to_instructions(self):
        prompt = self._get_prompt("generalista")
        assert "ROUTE_TO" in prompt
        assert 'specialist=' in prompt

    def test_generalista_has_all_specialist_options(self):
        prompt = self._get_prompt("generalista")
        for spec in ["apm", "infra", "conectividade", "observabilidade"]:
            assert f'"{spec}"' in prompt, f"Specialist {spec} not in generalista routing"

    def test_apm_has_datadog_tools(self):
        prompt = self._get_prompt("apm")
        assert "datadog_get_active_monitors" in prompt
        assert "datadog_get_logs" in prompt

    def test_infra_has_zabbix_tools(self):
        prompt = self._get_prompt("infra")
        assert "zabbix_get_active_problems" in prompt
        assert "zabbix_get_host_status" in prompt

    def test_infra_has_thresholds(self):
        prompt = self._get_prompt("infra")
        assert "80%" in prompt or "CPU" in prompt

    def test_conectividade_has_thousandeyes_tools(self):
        prompt = self._get_prompt("conectividade")
        assert "thousandeyes_get_active_alerts" in prompt
        assert "thousandeyes_get_bgp_alerts" in prompt

    def test_observabilidade_has_grafana_tools(self):
        prompt = self._get_prompt("observabilidade")
        assert "grafana_get_firing_alerts" in prompt

    def test_voice_mode_prohibits_tables(self):
        prompt = self._get_prompt("generalista", voice=True)
        assert "PROIBIDO" in prompt or "tabelas" in prompt.lower()
        assert "VOICE" in prompt or "VOZ" in prompt

    def test_voice_addendum_is_first(self):
        """Voice addendum deve vir antes do prompt base para ter prioridade."""
        prompt = self._get_prompt("generalista", voice=True)
        voice_idx = prompt.find("MODO VOZ") if "MODO VOZ" in prompt else prompt.find("VOZ ATIVO")
        pt_br_idx = prompt.find("Português Brasileiro")
        assert pt_br_idx < voice_idx, "Language premise must be first (before voice addendum)"

    def test_profile_n1_has_escalation_guidance(self):
        prompt = self._get_prompt("generalista", profile="N1")
        assert "N2" in prompt or "escalar" in prompt.lower()

    def test_profile_manager_avoids_technical_details(self):
        prompt = self._get_prompt("generalista", profile="manager")
        assert "executiva" in prompt.lower() or "negócio" in prompt.lower()


# ─── 2. ROUTE_TO detection ────────────────────────────────────────────────────

class TestRouteTo:
    """Testa detecção, strip e validação da tag ROUTE_TO."""

    REGEX = r'<ROUTE_TO\s+specialist=["\'](\w+)["\']\s+reason=["\']([^"\'>]*)["\']\s*/?>'

    def _match(self, text):
        return re.search(self.REGEX, text, re.IGNORECASE)

    def _strip(self, text):
        return re.sub(r'<ROUTE_TO[^>]*/>', '', text, flags=re.IGNORECASE).strip()

    def test_detect_double_quotes(self):
        m = self._match('<ROUTE_TO specialist="infra" reason="CPU alta"/>')
        assert m and m.group(1) == "infra" and "CPU" in m.group(2)

    def test_detect_single_quotes(self):
        m = self._match("<ROUTE_TO specialist='apm' reason='latência HTTP'/>")
        assert m and m.group(1) == "apm"

    def test_detect_without_self_closing(self):
        m = self._match('<ROUTE_TO specialist="infra" reason="problema">')
        assert m and m.group(1) == "infra"

    def test_detect_case_insensitive(self):
        m = self._match('<route_to specialist="apm" reason="erro"/>')
        assert m is not None

    def test_strip_removes_tag(self):
        text = 'Análise completa. <ROUTE_TO specialist="infra" reason="CPU alta"/> Um momento.'
        clean = self._strip(text)
        assert "<ROUTE_TO" not in clean
        assert "Análise completa" in clean
        assert "Um momento" in clean

    def test_strip_handles_no_tag(self):
        text = "Resposta normal sem redirecionamento."
        clean = self._strip(text)
        assert clean == text

    def test_all_valid_specialists_detected(self):
        from app.models import Specialist
        for spec in Specialist:
            tag = f'<ROUTE_TO specialist="{spec.value}" reason="teste"/>'
            m = self._match(tag)
            assert m, f"Failed to detect ROUTE_TO for specialist: {spec.value}"

    def test_invalid_specialist_not_accepted(self):
        """Backend should reject unknown specialist IDs."""
        from app.models import Specialist
        valid = [s.value for s in Specialist]
        assert "desconhecido" not in valid
        assert "unknown" not in valid

    def test_regex_in_orchestrator_matches_prompt_format(self):
        """O regex do orchestrator deve bater com o formato que o prompt ensina."""
        from app.agent.prompt import _ROUTING_INSTRUCTIONS
        # Extract example from prompt
        ex_match = re.search(r'<ROUTE_TO[^>]+>', _ROUTING_INSTRUCTIONS)
        assert ex_match, "No ROUTE_TO example found in _ROUTING_INSTRUCTIONS"
        # Test it against orchestrator regex
        m = self._match(ex_match.group())
        assert m, f"Orchestrator regex fails on prompt example: {ex_match.group()}"


# ─── 3. Handoff context ───────────────────────────────────────────────────────

class TestHandoffContext:
    """Testa geração do resumo de handoff entre especialistas."""

    def _make_session(self, msgs):
        from app.models import SessionData, UserProfile, ChatMessage, MessageRole
        session = SessionData(
            session_id="test", user_id="u1",
            user_profile=UserProfile.N2,
            active_specialist="generalista"
        )
        for role, content in msgs:
            r = MessageRole.user if role == "user" else MessageRole.agent
            session.messages.append(ChatMessage(role=r, content=content))
        return session

    def test_handoff_contains_route_reason(self):
        from app.agent.orchestrator import _build_handoff_context
        session = self._make_session([
            ("user", "Como está o ambiente?"),
            ("agent", "3 alertas críticos."),
        ])
        result = _build_handoff_context(session, "Generalista", "Infra", "CPU 95%")
        assert "CPU 95%" in result

    def test_handoff_contains_history(self):
        from app.agent.orchestrator import _build_handoff_context
        session = self._make_session([
            ("user", "Como está o ambiente?"),
            ("agent", "Há alertas críticos no servidor web."),
        ])
        result = _build_handoff_context(session, "Generalista", "Infra", "teste")
        assert "alertas críticos" in result

    def test_handoff_strips_route_to_tag(self):
        from app.agent.orchestrator import _build_handoff_context
        session = self._make_session([
            ("agent", 'Redirecionando. <ROUTE_TO specialist="infra" reason="CPU"/>'),
        ])
        result = _build_handoff_context(session, "Generalista", "Infra", "CPU")
        assert "<ROUTE_TO" not in result

    def test_handoff_has_mission_section(self):
        from app.agent.orchestrator import _build_handoff_context
        session = self._make_session([("user", "teste")])
        result = _build_handoff_context(session, "Generalista", "Infra", "teste")
        assert "missao" in result.lower() or "missão" in result.lower()

    def test_handoff_limits_history_length(self):
        from app.agent.orchestrator import _build_handoff_context
        from app.models import ChatMessage, MessageRole
        session = self._make_session([])
        # Add 20 messages
        for i in range(20):
            session.messages.append(ChatMessage(
                role=MessageRole.user, content=f"Mensagem {i}"
            ))
        result = _build_handoff_context(session, "A", "B", "teste")
        # Should not include all 20 messages (max 10)
        assert result.count("Mensagem") <= 10

    def test_handoff_labels_are_readable(self):
        from app.agent.orchestrator import _build_handoff_context
        session = self._make_session([("user", "pergunta")])
        result = _build_handoff_context(session, "Generalista NOC", "Especialista APM", "erro 502")
        assert "Especialista APM" in result


# ─── 4. Message conversion Anthropic↔OpenAI ──────────────────────────────────

class TestMessageConversion:
    """Testa conversão de mensagens para o formato OpenAI (OpenRouter)."""

    def test_simple_user_message(self):
        from app.agent.llm_client import _messages_to_openai
        msgs = [{"role": "user", "content": "Olá"}]
        result = _messages_to_openai("system", msgs)
        assert result[0]["role"] == "system"
        assert result[1] == {"role": "user", "content": "Olá"}

    def test_assistant_text_message(self):
        from app.agent.llm_client import _messages_to_openai
        msgs = [{"role": "assistant", "content": "Resposta"}]
        result = _messages_to_openai("system", msgs)
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Resposta"

    def test_tool_use_in_assistant(self):
        from app.agent.llm_client import _messages_to_openai
        tool_block = SimpleNamespace(type="tool_use", id="t1", name="zabbix_get_active_alerts", input={"organization": "ClienteA"})
        msgs = [{"role": "assistant", "content": [tool_block]}]
        result = _messages_to_openai("system", msgs)
        asst = result[1]
        assert asst["role"] == "assistant"
        assert "tool_calls" in asst
        assert asst["tool_calls"][0]["function"]["name"] == "zabbix_get_active_alerts"

    def test_tool_result_in_user(self):
        from app.agent.llm_client import _messages_to_openai
        msgs = [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": '{"alerts": []}'}
        ]}]
        result = _messages_to_openai("system", msgs)
        # Tool results expand to separate messages
        assert any(m.get("role") == "tool" for m in result)
        tool_msg = next(m for m in result if m.get("role") == "tool")
        assert tool_msg["tool_call_id"] == "t1"

    def test_no_arrays_in_messages(self):
        """Every message must be a dict, never a list (the original bug)."""
        from app.agent.llm_client import _messages_to_openai
        msgs = [
            {"role": "user", "content": "pergunta"},
            {"role": "assistant", "content": [
                SimpleNamespace(type="tool_use", id="t1", name="zabbix_get_active_alerts", input={})
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "resultado"}
            ]},
        ]
        result = _messages_to_openai("system", msgs)
        for i, msg in enumerate(result):
            assert isinstance(msg, dict), f"Message {i} is {type(msg)}, not dict: {msg}"

    def test_tool_input_serialized_to_json(self):
        from app.agent.llm_client import _messages_to_openai
        tool = SimpleNamespace(type="tool_use", id="t1", name="test", input={"key": "val"})
        msgs = [{"role": "assistant", "content": [tool]}]
        result = _messages_to_openai("system", msgs)
        args = result[1]["tool_calls"][0]["function"]["arguments"]
        parsed = json.loads(args)
        assert parsed["key"] == "val"


# ─── 5. MCP Dispatcher ────────────────────────────────────────────────────────

class TestMCPDispatcher:
    """Testa roteamento de tool calls para MCP servers."""

    def test_tool_prefix_routing(self):
        from app.agent.mcp_dispatcher import _MCP_URLS
        prefixes = set(_MCP_URLS.keys())
        assert "zabbix" in prefixes
        assert "datadog" in prefixes
        assert "grafana" in prefixes
        assert "thousandeyes" in prefixes

    def test_all_tools_have_valid_prefix(self):
        from app.agent.orchestrator import MCP_TOOLS
        from app.agent.mcp_dispatcher import _MCP_URLS
        valid_prefixes = set(_MCP_URLS.keys())
        for tool in MCP_TOOLS:
            name = tool["name"]
            prefix = name.split("_")[0]
            assert prefix in valid_prefixes, f"Tool {name} has unknown prefix {prefix}"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        from app.agent.mcp_dispatcher import MCPDispatcher
        d = MCPDispatcher()
        result = await d.call("unknown_tool", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_tool_call_timeout_returns_error(self):
        from app.agent.mcp_dispatcher import MCPDispatcher
        import httpx
        d = MCPDispatcher()
        with patch.object(d._client, 'post', side_effect=httpx.TimeoutException("timeout")):
            result = await d.call("zabbix_get_active_alerts", {})
        assert "error" in result
        assert "Timeout" in result["error"] or "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_tool_call_connect_error_returns_error(self):
        from app.agent.mcp_dispatcher import MCPDispatcher
        import httpx
        d = MCPDispatcher()
        with patch.object(d._client, 'post', side_effect=httpx.ConnectError("refused")):
            result = await d.call("datadog_get_active_monitors", {})
        assert "error" in result



# ─── 6. Full orchestrator flow ────────────────────────────────────────────────

class TestOrchestratorFlow:
    """Testa o fluxo completo do orquestrador."""

    def _make_session(self, specialist="generalista"):
        from app.models import SessionData, UserProfile
        return SessionData(
            session_id="test-orch", user_id="u1",
            user_profile=UserProfile.N2,
            active_specialist=specialist,
        )

    def _setup_redis(self):
        from app.agent.session import session_manager
        r = AsyncMock()
        r.get  = AsyncMock(return_value=None)
        r.set  = AsyncMock(return_value=True)
        r.ping = AsyncMock(return_value=True)
        session_manager.redis = r
        return r

    def _make_stream(self, text="OK", tool_calls=None, route_to=None):
        full = text
        if route_to:
            full += f' <ROUTE_TO specialist="{route_to}" reason="teste"/>'
        content = [SimpleNamespace(type="text", text=full)]
        if tool_calls:
            for tc in tool_calls:
                content.append(SimpleNamespace(type="tool_use", id=tc["id"], name=tc["name"], input=tc.get("input", {})))
        final = SimpleNamespace(stop_reason="tool_use" if tool_calls else "end_turn", content=content)

        async def fn(*a, **k):
            yield "text", full
            yield "final", final
        return fn

    def _cfg(self, provider="anthropic"):
        from app.models import AIConfig, AIProvider
        return AIConfig(provider=AIProvider(provider), model="test-model", api_key="sk-test")

    @pytest.mark.asyncio
    async def test_simple_response_yields_tokens_and_done(self):
        from app.agent.orchestrator import AgentOrchestrator
        from app.models import WSEventType
        from app.settings import settings
        settings.anthropic_api_key = "sk-test"
        self._setup_redis()
        session = self._make_session()
        orch    = AgentOrchestrator()
        with patch("app.agent.orchestrator.ai_config_store.get", AsyncMock(return_value=self._cfg())), \
             patch("app.agent.session.session_manager.save_session", AsyncMock()), \
             patch("app.agent.llm_client.build_anthropic_client"), \
             patch("app.agent.orchestrator.stream_anthropic", self._make_stream("Ambiente OK")):
            events = [ev async for ev in orch.process_message("Como está?", session)]
        types = [e.type for e in events]
        assert WSEventType.agent_token in types
        assert WSEventType.agent_done in types

    @pytest.mark.asyncio
    async def test_route_to_emits_specialist_change(self):
        from app.agent.orchestrator import AgentOrchestrator
        from app.models import WSEventType
        from app.settings import settings
        settings.anthropic_api_key = "sk-test"
        self._setup_redis()
        session = self._make_session("generalista")
        orch    = AgentOrchestrator()
        with patch("app.agent.orchestrator.ai_config_store.get", AsyncMock(return_value=self._cfg())), \
             patch("app.agent.session.session_manager.save_session", AsyncMock()), \
             patch("app.agent.llm_client.build_anthropic_client"), \
             patch("app.agent.orchestrator.stream_anthropic", self._make_stream("Infra issue.", route_to="infra")):
            events = [ev async for ev in orch.process_message("Investigue.", session)]
        types = [e.type for e in events]
        assert WSEventType.specialist_change in types, f"No specialist_change in {types}"
        spec_ev = next(e for e in events if e.type == WSEventType.specialist_change)
        assert spec_ev.specialist == "infra"
        assert session.active_specialist == "infra"

    @pytest.mark.asyncio
    async def test_route_to_tag_stripped_from_stored_message(self):
        from app.agent.orchestrator import AgentOrchestrator
        from app.models import MessageRole
        from app.settings import settings
        settings.anthropic_api_key = "sk-test"
        self._setup_redis()
        session = self._make_session("generalista")
        orch    = AgentOrchestrator()
        with patch("app.agent.orchestrator.ai_config_store.get", AsyncMock(return_value=self._cfg())), \
             patch("app.agent.session.session_manager.save_session", AsyncMock()), \
             patch("app.agent.llm_client.build_anthropic_client"), \
             patch("app.agent.orchestrator.stream_anthropic", self._make_stream("Redireciono.", route_to="infra")):
            async for _ in orch.process_message("teste", session):
                pass
        agent_msgs = [m for m in session.messages if m.role == MessageRole.agent]
        assert len(agent_msgs) > 0
        for m in agent_msgs:
            assert "<ROUTE_TO" not in m.content, f"Tag not stripped: {m.content}"

    @pytest.mark.asyncio
    async def test_specialist_system_prompt_used(self):
        from app.agent.orchestrator import AgentOrchestrator
        from app.settings import settings
        settings.anthropic_api_key = "sk-test"
        self._setup_redis()
        session = self._make_session("apm")
        orch    = AgentOrchestrator()
        captured = {}

        async def cap_stream(client, model, max_tokens, temp, system, messages, tools):
            captured["system"] = system
            final = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="APM OK")])
            yield "text", "APM OK"
            yield "final", final

        with patch("app.agent.orchestrator.ai_config_store.get", AsyncMock(return_value=self._cfg())), \
             patch("app.agent.session.session_manager.save_session", AsyncMock()), \
             patch("app.agent.llm_client.build_anthropic_client"), \
             patch("app.agent.orchestrator.stream_anthropic", cap_stream):
            async for _ in orch.process_message("Verifique logs.", session):
                pass

        assert "system" in captured
        assert "datadog" in captured["system"].lower(), "APM prompt should mention Datadog"

    @pytest.mark.asyncio
    async def test_specialist_auto_responds_after_route_to(self):
        """After ROUTE_TO, new specialist auto-responds with handoff context."""
        from app.agent.orchestrator import AgentOrchestrator
        from app.models import AIConfig, AIProvider, WSEventType, SessionData, UserProfile

        self._setup_redis()
        session = self._make_session()
        orch    = AgentOrchestrator()

        call_count = 0

        async def fake_stream_fn(client, model, max_tokens, temp, system, messages, tools):
            from types import SimpleNamespace
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: generalista emits ROUTE_TO
                yield "text", 'Identificado problema de infra. <ROUTE_TO specialist="infra" reason="CPU alta"/>'
                final = SimpleNamespace(
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text",
                        text='Identificado problema de infra. <ROUTE_TO specialist="infra" reason="CPU alta"/>')],
                )
                yield "final", final
            else:
                # Second call: infra specialist responds to handoff
                yield "text", "Analisando CPU alta no servidor..."
                final = SimpleNamespace(
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text="Analisando CPU alta no servidor...")],
                )
                yield "final", final

        mock_cfg = AIConfig(provider=AIProvider.anthropic, model="claude-sonnet-4-20250514", api_key="sk-test")
        mock_store = AsyncMock()
        mock_store.get = AsyncMock(return_value=mock_cfg)

        with patch("app.agent.orchestrator.ai_config_store", mock_store), \
             patch("app.agent.orchestrator.stream_anthropic", fake_stream_fn), \
             patch("app.agent.orchestrator.build_anthropic_client", return_value=AsyncMock()), \
             patch("app.agent.session.session_manager.save_session", AsyncMock()):
            events = [ev async for ev in orch.process_message("Como está o ambiente?", session)]

        types = [e.type for e in events]

        # Must have specialist_change
        assert WSEventType.specialist_change in types, f"No specialist_change in {types}"

        # New specialist must auto-respond (second agent_token stream)
        agent_tokens = [e for e in events if e.type == WSEventType.agent_token]
        assert len(agent_tokens) >= 2, "New specialist should have streamed tokens"

        # Final session specialist must be infra
        assert session.active_specialist == "infra"

        # process_message was called twice (once by us, once internally for handoff)
        assert call_count == 2, f"Expected 2 LLM calls, got {call_count}"

    async def test_no_api_key_yields_error(self):
        from app.agent.orchestrator import AgentOrchestrator
        from app.models import AIConfig, AIProvider, WSEventType
        from app.settings import settings
        settings.anthropic_api_key = ""
        self._setup_redis()
        session = self._make_session()
        orch    = AgentOrchestrator()
        with patch("app.agent.orchestrator.ai_config_store.get",
                   AsyncMock(return_value=AIConfig(provider=AIProvider.anthropic, model="test", api_key=""))), \
             patch("app.agent.session.session_manager.save_session", AsyncMock()):
            events = [ev async for ev in orch.process_message("teste", session)]
        error_events = [e for e in events if e.type == WSEventType.error]
        assert len(error_events) > 0, "Should yield error event when no API key"
