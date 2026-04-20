"""
LLM Client factory.
- Anthropic provider  → uses anthropic.AsyncAnthropic (native SDK)
- OpenRouter provider → uses openai.AsyncOpenAI (OpenAI-compatible API)

The Anthropic SDK has a host allowlist and rejects openrouter.ai.
OpenRouter is OpenAI-compatible, so we use the OpenAI SDK for it.
"""
import json
import os
from typing import Any, AsyncGenerator
import httpx
import structlog

log = structlog.get_logger()


def _ssl_verify(is_openrouter: bool) -> bool:
    if is_openrouter:
        return os.environ.get("OPENROUTER_SSL_VERIFY",
               os.environ.get("ANTHROPIC_SSL_VERIFY", "false")).lower() != "false"
    return os.environ.get("ANTHROPIC_SSL_VERIFY", "true").lower() != "false"


def _http_client(verify: bool, timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        verify=verify,
        timeout=httpx.Timeout(timeout, connect=30.0),
    )


def build_anthropic_client(api_key: str):
    from anthropic import AsyncAnthropic
    return AsyncAnthropic(
        api_key=api_key,
        http_client=_http_client(_ssl_verify(False), 60.0),
    )


def build_openrouter_client(api_key: str, base_url: str,
                             site_name: str = "", site_url: str = ""):
    from openai import AsyncOpenAI
    headers = {
        "HTTP-Referer": site_url or "https://noc-ai-chat.local",
        "X-Title":      site_name or "NOC AI Chat",
    }
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers=headers,
        http_client=_http_client(_ssl_verify(True), 120.0),
    )


# ─── Anthropic streaming ──────────────────────────────────────────────────────

async def stream_anthropic(client, model: str, max_tokens: int,
                            temperature: float, system: str,
                            messages: list, tools: list) -> AsyncGenerator[tuple[str, Any], None]:
    """Yields ('text', str) | ('final', message)"""
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=tools,       # type: ignore
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield "text", text
        final = await stream.get_final_message()
        yield "final", final


# ─── OpenRouter streaming ─────────────────────────────────────────────────────

async def stream_openrouter(client, model: str, max_tokens: int,
                             temperature: float, system: str,
                             messages: list, tools: list) -> AsyncGenerator[tuple[str, Any], None]:
    """Same interface as stream_anthropic but uses OpenAI-compatible API."""

    oai_tools    = [_tool_to_openai(t) for t in tools] if tools else []
    oai_messages = _messages_to_openai(system, messages)

    collected_text  = ""
    tool_calls_raw: dict[int, dict] = {}

    stream = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=oai_messages,
        tools=oai_tools if oai_tools else None,
        stream=True,
    )

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        if delta.content:
            collected_text += delta.content
            yield "text", delta.content

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_raw:
                    tool_calls_raw[idx] = {"id": "", "name": "", "arguments": ""}
                if tc.id:
                    tool_calls_raw[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        tool_calls_raw[idx]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_calls_raw[idx]["arguments"] += tc.function.arguments

    yield "final", _make_final_message(collected_text, tool_calls_raw)


# ─── Format converters ────────────────────────────────────────────────────────

def _tool_to_openai(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name":        tool["name"],
            "description": tool.get("description", ""),
            "parameters":  tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


def _messages_to_openai(system: str, messages: list) -> list:
    """
    Convert list of Anthropic-format messages to OpenAI format.
    Anthropic format stores tool_results as user messages with list content.
    OpenAI expects each tool result as a separate {"role": "tool", ...} message.
    """
    result = [{"role": "system", "content": system}]

    for msg in messages:
        converted = _msg_to_openai(msg)
        if isinstance(converted, list):
            # tool_results expand into multiple messages
            result.extend(converted)
        else:
            result.append(converted)

    return result


def _msg_to_openai(msg: dict) -> Any:
    """
    Convert a single Anthropic message to OpenAI format.
    May return a list of messages (for tool_result blocks).
    """
    role    = msg.get("role", "user")
    content = msg.get("content", "")

    # Simple text message
    if isinstance(content, str):
        return {"role": role, "content": content}

    if not isinstance(content, list):
        return {"role": role, "content": str(content)}

    # Assistant message with tool_use blocks
    if role == "assistant":
        text_parts = []
        tool_calls = []
        for block in content:
            btype = block.type if hasattr(block, "type") else block.get("type", "")
            if btype == "text":
                text = block.text if hasattr(block, "text") else block.get("text", "")
                if text:
                    text_parts.append(text)
            elif btype == "tool_use":
                bid  = block.id   if hasattr(block, "id")   else block.get("id", "")
                name = block.name if hasattr(block, "name") else block.get("name", "")
                inp  = block.input if hasattr(block, "input") else block.get("input", {})
                tool_calls.append({
                    "id":       bid,
                    "type":     "function",
                    "function": {"name": name, "arguments": json.dumps(inp)},
                })
        out: dict = {"role": "assistant"}
        if text_parts:
            out["content"] = " ".join(text_parts)
        if tool_calls:
            out["tool_calls"] = tool_calls
        return out

    # User message that may contain tool_result blocks
    if role == "user":
        tool_msgs = []
        text_parts = []
        for item in content:
            itype = item.get("type", "") if isinstance(item, dict) else ""
            if itype == "tool_result":
                tool_content = item.get("content", "")
                if isinstance(tool_content, list):
                    # Flatten list content to string
                    tool_content = " ".join(
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in tool_content
                    )
                tool_msgs.append({
                    "role":         "tool",
                    "tool_call_id": item.get("tool_use_id", ""),
                    "content":      str(tool_content),
                })
            elif itype == "text":
                text_parts.append(item.get("text", ""))

        if tool_msgs:
            # If there's also text, prepend it as a user message
            if text_parts:
                return [{"role": "user", "content": " ".join(text_parts)}] + tool_msgs
            return tool_msgs

    return {"role": role, "content": str(content)}


def _make_final_message(text: str, tool_calls_raw: dict):
    """Build a synthetic final message compatible with the orchestrator."""
    from types import SimpleNamespace

    stop_reason = "tool_use" if tool_calls_raw else "end_turn"
    content     = []

    if text:
        content.append(SimpleNamespace(type="text", text=text))

    for tc in tool_calls_raw.values():
        try:
            inp = json.loads(tc["arguments"] or "{}")
        except Exception:
            inp = {}
        content.append(SimpleNamespace(
            type="tool_use",
            id=tc["id"],
            name=tc["name"],
            input=inp,
        ))

    return SimpleNamespace(stop_reason=stop_reason, content=content)
