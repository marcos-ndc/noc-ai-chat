"""
Router: Admin Panel
Endpoints de administração — requer perfil admin.
Gerencia configuração de IA e system prompts em runtime.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.agent.ai_config import ai_config_store
from app.auth.service import auth_service
from app.models import (
    AIConfig, AIConfigOut, AIProvider,
    ModelOption, UserOut, UserProfile,
)
from app.settings import settings

router = APIRouter(prefix="/admin", tags=["admin"])
log    = structlog.get_logger()
_bearer = HTTPBearer()


# ─── Auth guard ───────────────────────────────────────────────────────────────

def require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> UserOut:
    user = auth_service.get_user_from_token(creds.credentials)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    if user.profile != UserProfile.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acesso restrito a administradores")
    return user


# ─── Model catalog ────────────────────────────────────────────────────────────

MODELS: list[ModelOption] = [
    # ── Anthropic (direto) ────────────────────────────────────────────────────
    ModelOption(id="claude-opus-4-5",           name="Claude Opus 4.5",           provider=AIProvider.anthropic,  description="Mais poderoso — raciocínio profundo e tarefas complexas",          context_k=200),
    ModelOption(id="claude-sonnet-4-5",         name="Claude Sonnet 4.5",         provider=AIProvider.anthropic,  description="Equilíbrio ideal velocidade/qualidade (recomendado)",              context_k=200),
    ModelOption(id="claude-sonnet-4-20250514",  name="Claude Sonnet 4 (stable)",  provider=AIProvider.anthropic,  description="Versão estável e confiável do Sonnet 4",                          context_k=200),
    ModelOption(id="claude-haiku-4-5-20251001", name="Claude Haiku 4.5",          provider=AIProvider.anthropic,  description="Mais rápido e econômico — triagem e respostas simples",           context_k=200),

    # ── OpenRouter — Anthropic ────────────────────────────────────────────────
    ModelOption(id="anthropic/claude-opus-4-5",          name="Claude Opus 4.5 (OR)",   provider=AIProvider.openrouter, description="Claude Opus via OpenRouter",                               context_k=200),
    ModelOption(id="anthropic/claude-sonnet-4-5",        name="Claude Sonnet 4.5 (OR)", provider=AIProvider.openrouter, description="Claude Sonnet via OpenRouter — recomendado",               context_k=200),
    ModelOption(id="anthropic/claude-haiku-4-5",         name="Claude Haiku 4.5 (OR)",  provider=AIProvider.openrouter, description="Claude Haiku via OpenRouter — rápido e barato",            context_k=200),

    # ── OpenRouter — OpenAI ───────────────────────────────────────────────────
    ModelOption(id="openai/gpt-4o",             name="GPT-4o",               provider=AIProvider.openrouter, description="GPT-4o — multimodal, rápido e capaz",                              context_k=128),
    ModelOption(id="openai/gpt-4o-mini",        name="GPT-4o Mini",          provider=AIProvider.openrouter, description="GPT-4o Mini — mais leve e econômico",                              context_k=128),
    ModelOption(id="openai/gpt-oss-120b",       name="GPT-OSS 120B",         provider=AIProvider.openrouter, description="Primeiro modelo open-weight da OpenAI — Apache 2.0, grátis",       context_k=128),

    # ── OpenRouter — Google ───────────────────────────────────────────────────
    ModelOption(id="google/gemini-2.5-flash-lite", name="Gemini 2.5 Flash Lite", provider=AIProvider.openrouter, description="Google Gemini — mais rápido e barato da família 2.5",          context_k=1000),
    ModelOption(id="google/gemini-2.0-flash-001",  name="Gemini 2.0 Flash",      provider=AIProvider.openrouter, description="Google Gemini 2.0 Flash — velocidade e qualidade",             context_k=1000),

    # ── OpenRouter — Meta ─────────────────────────────────────────────────────
    ModelOption(id="meta-llama/llama-3.3-70b-instruct", name="Llama 3.3 70B",   provider=AIProvider.openrouter, description="Meta Llama 3.3 70B — open source, nível GPT-4, grátis",        context_k=128),
    ModelOption(id="meta-llama/llama-3.1-8b-instruct",  name="Llama 3.1 8B",    provider=AIProvider.openrouter, description="Llama 3.1 8B — leve, grátis, bom para tarefas simples",        context_k=128),

    # ── OpenRouter — Mistral ──────────────────────────────────────────────────
    ModelOption(id="mistralai/mistral-large-2512",           name="Mistral Large 3",      provider=AIProvider.openrouter, description="Mistral Large 3 — 675B total, 41B ativo (MoE), Apache 2.0", context_k=262),
    ModelOption(id="mistralai/mistral-small-3.2-24b-instruct-2506", name="Mistral Small 3.2", provider=AIProvider.openrouter, description="Mistral Small 3.2 24B — equilibrado, bom custo-benefício", context_k=128),

    # ── OpenRouter — DeepSeek ─────────────────────────────────────────────────
    ModelOption(id="deepseek/deepseek-r1",      name="DeepSeek R1",          provider=AIProvider.openrouter, description="DeepSeek R1 — raciocínio avançado, grátis (tier free disponível)", context_k=164),

    # ── OpenRouter — NVIDIA ───────────────────────────────────────────────────
    ModelOption(id="nvidia/nemotron-3-super-120b-a12b", name="NVIDIA Nemotron 3 Super 120B", provider=AIProvider.openrouter, description="MoE 120B, ativa 12B, 262K ctx — grátis (não use :free no ID)", context_k=262),

    # ── OpenRouter — Qwen ─────────────────────────────────────────────────────
    ModelOption(id="qwen/qwen3-235b-a22b",      name="Qwen3 235B",           provider=AIProvider.openrouter, description="Qwen3 MoE 235B — ótimo raciocínio, grátis",                       context_k=128),
]

# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_models(_: UserOut = Depends(require_admin)) -> list[ModelOption]:
    """Lista todos os modelos disponíveis por provedor."""
    return MODELS


@router.get("/ai-config")
async def get_ai_config(_: UserOut = Depends(require_admin)) -> AIConfigOut:
    """Retorna configuração atual de IA com API key mascarada."""
    cfg = await ai_config_store.get()
    key = cfg.api_key or (settings.anthropic_api_key if cfg.provider == AIProvider.anthropic else "")
    preview = (key[:12] + "..." + key[-4:]) if len(key) > 16 else ("***" if key else "")
    return AIConfigOut(
        provider=cfg.provider,
        model=cfg.model,
        api_key_set=bool(key),
        api_key_preview=preview,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        openrouter_base_url=cfg.openrouter_base_url,
        site_name=cfg.site_name,
    )


@router.put("/ai-config")
async def update_ai_config(
    body: AIConfig,
    user: UserOut = Depends(require_admin),
) -> AIConfigOut:
    """Atualiza configuração de IA em runtime (sem reiniciar o stack)."""
    # If api_key is empty string, keep existing key
    if not body.api_key:
        existing = await ai_config_store.get()
        body.api_key = existing.api_key

    await ai_config_store.save(body)
    ai_config_store.invalidate_cache()

    log.info("admin.ai_config_updated",
             provider=body.provider,
             model=body.model,
             user=user.email)

    return await get_ai_config(user)


@router.post("/ai-config/test")
async def test_ai_config(
    _: UserOut = Depends(require_admin),
) -> dict:
    """Testa a configuração atual enviando uma mensagem simples."""
    from anthropic import AsyncAnthropic
    from app.agent.orchestrator import orchestrator

    cfg = await ai_config_store.get()
    api_key = cfg.api_key or settings.anthropic_api_key

    if not api_key:
        return {"success": False, "error": "API key não configurada"}

    is_openrouter = cfg.provider == AIProvider.openrouter
    try:
        if is_openrouter:
            from app.agent.llm_client import build_openrouter_client
            client = build_openrouter_client(
                api_key,
                cfg.openrouter_base_url,
                site_name=cfg.site_name,
                site_url=cfg.site_url,
            )
            resp = await client.chat.completions.create(
                model=cfg.model,
                max_tokens=50,
                messages=[{"role": "user", "content": "Responda apenas: OK"}],
            )
            reply = resp.choices[0].message.content or "" if resp.choices else ""
            usage = resp.usage
            return {
                "success":       True,
                "provider":      cfg.provider,
                "model":         cfg.model,
                "response":      reply,
                "input_tokens":  usage.prompt_tokens     if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
            }
        else:
            from app.agent.llm_client import build_anthropic_client
            import anthropic as _anthropic
            client = build_anthropic_client(api_key)
            resp = await client.messages.create(
                model=cfg.model,
                max_tokens=50,
                messages=[{"role": "user", "content": "Responda apenas: OK"}],
            )
            reply = resp.content[0].text if resp.content else ""
            return {
                "success":       True,
                "provider":      cfg.provider,
                "model":         cfg.model,
                "response":      reply,
                "input_tokens":  resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }

    except Exception as e:
        import re as _re
        err_raw  = str(e)
        err_type = type(e).__name__

        # Detect error type by class name (works for both Anthropic and OpenAI SDKs)
        err_lower = err_raw.lower()
        if "notfound" in err_type.lower() or "404" in err_raw:
            short = f"Modelo '{cfg.model}' não encontrado em {cfg.provider}."
            hint  = ("Verifique o ID do modelo. OpenRouter usa formato 'provedor/modelo'. "
                     "Consulte a lista completa em openrouter.ai/models")
        elif "authentication" in err_type.lower() or "401" in err_raw or "invalid_api_key" in err_lower:
            short = "API key inválida ou expirada."
            hint  = ("Chaves OpenRouter começam com 'sk-or-v1-'. Gere em openrouter.ai/keys"
                     if is_openrouter else "Verifique em console.anthropic.com")
        elif "permission" in err_type.lower() or "403" in err_raw or "host not in allowlist" in err_lower:
            short = "Sem permissão."
            hint  = ("Adicione HTTP-Referer no campo Site URL do painel admin."
                     if is_openrouter else "Verifique os limites do seu plano Anthropic.")
        elif "ratelimit" in err_type.lower() or "429" in err_raw:
            short = "Limite de requisições atingido."
            hint  = "Aguarde alguns segundos e tente novamente."
        elif "timeout" in err_type.lower() or "timeout" in err_lower:
            short = "Timeout — proxy/firewall bloqueando a conexão."
            hint  = "Confirme que ANTHROPIC_SSL_VERIFY=false está no .env e reinicie o backend."
        elif "connection" in err_type.lower() or "ssl" in err_lower or "certificate" in err_lower:
            short = "Erro de conexão ou SSL."
            hint  = "Adicione ANTHROPIC_SSL_VERIFY=false no .env e reinicie o backend."
        else:
            err_clean = _re.sub(r"<[^>]+>", " ", err_raw)
            err_clean = _re.sub(r"\s{2,}", " ", err_clean).strip()[:150]
            short = err_clean
            hint  = "Verifique API key, ID do modelo e configurações de rede."

        return {
            "success":    False,
            "error":      short,
            "error_type": err_type,
            "hint":       hint,
            "provider":   cfg.provider,
            "model":      cfg.model,
        }


# ─── Prompt management ────────────────────────────────────────────────────────

_PROMPT_META: dict[str, dict] = {
    "specialist:generalista":     {"label": "Generalista NOC",          "category": "specialist"},
    "specialist:apm":             {"label": "Especialista APM & Logs",  "category": "specialist"},
    "specialist:infra":           {"label": "Especialista Infraestrutura", "category": "specialist"},
    "specialist:conectividade":   {"label": "Especialista Conectividade",  "category": "specialist"},
    "specialist:observabilidade": {"label": "Especialista Observabilidade","category": "specialist"},
    "profile:N1":       {"label": "Perfil N1 (Analista N1)",    "category": "profile"},
    "profile:N2":       {"label": "Perfil N2 (Analista N2)",    "category": "profile"},
    "profile:engineer": {"label": "Perfil Engineer (Engenheiro)","category": "profile"},
    "profile:manager":  {"label": "Perfil Manager (Gestor)",    "category": "profile"},
    "profile:admin":    {"label": "Perfil Admin",               "category": "profile"},
}


class PromptUpdate(BaseModel):
    text: str


@router.get("/prompts")
async def get_prompts(_: UserOut = Depends(require_admin)) -> list[dict]:
    """Lista todos os prompts com valores atuais (override ou padrão)."""
    from app.agent.prompt import get_default_prompts
    from app.agent.prompt_store import prompt_store

    defaults = get_default_prompts()
    result = []
    for key, meta in _PROMPT_META.items():
        default_text = defaults.get(key, "")
        override = await prompt_store.get_override(key)
        result.append({
            "key":          key,
            "label":        meta["label"],
            "category":     meta["category"],
            "default_text": default_text,
            "current_text": override if override is not None else default_text,
            "is_overridden": override is not None,
        })
    return result


@router.put("/prompts/{key:path}")
async def update_prompt(
    key: str,
    body: PromptUpdate,
    user: UserOut = Depends(require_admin),
) -> dict:
    """Salva um override para o prompt especificado."""
    if key not in _PROMPT_META:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' não encontrado")

    from app.agent.prompt_store import prompt_store
    await prompt_store.set_override(key, body.text)
    log.info("admin.prompt_updated", key=key, user=user.email)
    return {"ok": True, "key": key, "is_overridden": True}


@router.delete("/prompts/{key:path}")
async def reset_prompt(
    key: str,
    user: UserOut = Depends(require_admin),
) -> dict:
    """Remove o override, voltando ao prompt padrão."""
    if key not in _PROMPT_META:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' não encontrado")

    from app.agent.prompt_store import prompt_store
    await prompt_store.clear_override(key)
    log.info("admin.prompt_reset", key=key, user=user.email)
    return {"ok": True, "key": key, "is_overridden": False}


@router.get("/status")
async def admin_status(_: UserOut = Depends(require_admin)) -> dict:
    """Visão geral do sistema para o painel admin."""
    from app.agent.session import session_manager
    from app.agent.mcp_dispatcher import MCPDispatcher

    cfg = await ai_config_store.get()

    # Check Redis
    try:
        await session_manager.redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    # Check MCP health
    dispatcher = MCPDispatcher()
    mcp_status = {}
    for svc in ["zabbix", "datadog", "grafana", "thousandeyes"]:
        mcp_status[svc] = await dispatcher.health_check(svc)

    return {
        "ai": {
            "provider": cfg.provider,
            "model": cfg.model,
            "api_key_set": bool(cfg.api_key or settings.anthropic_api_key),
        },
        "redis": "ok" if redis_ok else "down",
        "mcp_servers": mcp_status,
    }
