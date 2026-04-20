"""
LLM Client factory.
- Anthropic provider  → uses anthropic.AsyncAnthropic (native SDK)
- OpenRouter provider → uses openai.AsyncOpenAI (OpenAI-compatible API)

The Anthropic SDK has a host allowlist and rejects openrouter.ai.
OpenRouter is OpenAI-compatible, so we use the OpenAI SDK for it.
"""
import os
from typing import Any, AsyncGenerator, Optional
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
    verify = _ssl_verify(False)
    return AsyncAnthropic(
        api_key=api_key,
        http_client=_http_client(verify, 60.0),
    )


def build_openrouter_client(api_key: str, base_url: str, site_name: str = "", site_url: str = ""):
    from openai import AsyncOpenAI
    verify  = _ssl_verify(True)
    headers = {"HTTP-Referer": site_url or "https://noc-ai-chat.local",
               "X-Title":      site_name or "NOC AI Chat"}
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers=headers,
        http_client=_http_client(verify, 120.0),
    )


# ─── Unified streaming interface ─────────────────────────────────────────────

async def stream_anthropic(client, model: str, max_tokens: int,
                           temperature: float, system: str,
                           messages: list, tools: list) -> AsyncGenerator[tuple[str, Any], None]:
    """Yields (type, data) tuples: ('text', str) | ('tool_use', block) | ('final', message)"""
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=tools,  # type: ignore
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield "text", text
        final = await stream.get_final_message()
        yield "final", final


async def stream_openrouter(client, model: str, max_tokens: int,
                            temperature: float, system: str,
                            messages: list, tools: list) -> AsyncGenerator[tuple[str, Any], None]:
    """Same interface as stream_anthropic but uses OpenAI-compatible API."""
    # Convert Anthropic tool format → OpenAI tool format
    oai_tools = [_anthropic_tool_to_openai(t) for t in tools]

    # Convert Anthropic messages format → OpenAI format
    oai_messages = [{"role": "system", "content": system}] + [
        _anthropic_msg_to_openai(m) for m in messages
    ]

    collected_text  = ""
    tool_calls_raw: dict = {}

    # OpenAI SDK: create() with stream=True returns an async iterable directly
    # Do NOT use async with — it's not a context manager
    stream = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=oai_messages,
        tools=oai_tools if oai_tools else None,
        stream=True,
    )
    async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Text tokens
            if delta.content:
                collected_text += delta.content
                yield "text", delta.content

            # Tool call deltas
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_raw[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_raw[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_raw[idx]["arguments"] += tc.function.arguments

    # Build a synthetic "final message" compatible with our orchestrator
    import json

    class FinalMessage:
        def __init__(self, text, tool_calls_raw):
            self.stop_reason = "tool_use" if tool_calls_raw else "end_turn"
            content = []
            if text:
                from types import SimpleNamespace
                content.append(SimpleNamespace(type="text", text=text))
            for tc in tool_calls_raw.values():
                try:
                    inp = json.loads(tc["arguments"] or "{}")
                except Exception:
                    inp = {}
                from types import SimpleNamespace
                content.append(SimpleNamespace(type="tool_use", id=tc["id"], name=tc["name"], input=inp))
            self.content = content

    yield "final", FinalMessage(collected_text, tool_calls_raw)


def _anthropic_tool_to_openai(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name":        tool["name"],
            "description": tool.get("description", ""),
            "parameters":  tool.get("input_schema", {"type": "object", "properties": {}}),
        }
    }


def _anthropic_msg_to_openai(msg: dict) -> dict:
    """Convert Anthropic message format to OpenAI format."""
    import json
    role    = msg["role"]
    content = msg["content"]

    if isinstance(content, str):
        return {"role": role, "content": content}

    if isinstance(content, list):
        # Tool use from assistant
        if role == "assistant":
            text_parts = [b.text for b in content if hasattr(b, "type") and b.type == "text"]
            tool_calls = []
            for b in content:
                if hasattr(b, "type") and b.type == "tool_use":
                    tool_calls.append({
                        "id":       b.id,
                        "type":     "function",
                        "function": {"name": b.name, "arguments": json.dumps(b.input)},
                    })
            result: dict = {"role": "assistant"}
            if text_parts:
                result["content"] = " ".join(text_parts)
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result

        # Tool results from user
        if role == "user":
            messages = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    messages.append({
                        "role":         "tool",
                        "tool_call_id": item["tool_use_id"],
                        "content":      item["content"],
                    })
            if messages:
                return messages  # type: ignore — caller must handle list

    return {"role": role, "content": str(content)}
