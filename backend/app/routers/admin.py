"""
Router: Admin Panel
Endpoints de administração — requer perfil admin.
Gerencia configuração de IA em runtime (provedor, modelo, API key).
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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
    # Anthropic
    ModelOption(id="claude-opus-4-5",            name="Claude Opus 4.5",          provider=AIProvider.anthropic,  description="Mais poderoso — análise profunda e raciocínio complexo",     context_k=200),
    ModelOption(id="claude-sonnet-4-5",          name="Claude Sonnet 4.5",        provider=AIProvider.anthropic,  description="Equilíbrio ideal entre velocidade e qualidade (recomendado)", context_k=200),
    ModelOption(id="claude-sonnet-4-20250514",   name="Claude Sonnet 4 (stable)", provider=AIProvider.anthropic,  description="Versão estável do Sonnet 4 — alta confiabilidade",             context_k=200),
    ModelOption(id="claude-haiku-4-5-20251001",  name="Claude Haiku 4.5",         provider=AIProvider.anthropic,  description="Mais rápido e econômico — respostas simples e triagem",        context_k=200),
    # OpenRouter — Anthropic via OR
    ModelOption(id="anthropic/claude-opus-4-5",           name="Claude Opus 4.5 (OR)",    provider=AIProvider.openrouter, description="Claude Opus via OpenRouter",                                   context_k=200),
    ModelOption(id="anthropic/claude-sonnet-4-5",         name="Claude Sonnet 4.5 (OR)",  provider=AIProvider.openrouter, description="Claude Sonnet via OpenRouter",                                 context_k=200),
    # OpenRouter — OpenAI
    ModelOption(id="openai/gpt-4o",              name="GPT-4o",                   provider=AIProvider.openrouter, description="OpenAI GPT-4o via OpenRouter",                                context_k=128),
    ModelOption(id="openai/gpt-4o-mini",         name="GPT-4o Mini",              provider=AIProvider.openrouter, description="GPT-4o Mini — rápido e econômico",                            context_k=128),
    ModelOption(id="openai/o1",                  name="OpenAI o1",                provider=AIProvider.openrouter, description="OpenAI o1 — raciocínio avançado",                             context_k=200),
    # OpenRouter — Google
    ModelOption(id="google/gemini-2.0-flash-001", name="Gemini 2.0 Flash",        provider=AIProvider.openrouter, description="Google Gemini 2.0 Flash — muito rápido",                     context_k=1000),
    ModelOption(id="google/gemini-pro-1.5",      name="Gemini Pro 1.5",           provider=AIProvider.openrouter, description="Google Gemini Pro 1.5",                                       context_k=1000),
    # OpenRouter — Meta / OSS
    ModelOption(id="meta-llama/llama-3.3-70b-instruct",  name="Llama 3.3 70B",   provider=AIProvider.openrouter, description="Meta Llama 3.3 70B — open source de alta qualidade",         context_k=128),
    ModelOption(id="meta-llama/llama-3.1-8b-instruct",   name="Llama 3.1 8B",    provider=AIProvider.openrouter, description="Llama 3.1 8B — rápido e leve",                               context_k=128),
    ModelOption(id="mistralai/mistral-large",    name="Mistral Large",            provider=AIProvider.openrouter, description="Mistral Large — excelente custo-benefício",                   context_k=128),
    ModelOption(id="deepseek/deepseek-r1",       name="DeepSeek R1",              provider=AIProvider.openrouter, description="DeepSeek R1 — raciocínio de alta qualidade",                 context_k=164),
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
        client = orchestrator._build_client(
            api_key,
            cfg.openrouter_base_url if is_openrouter else None,
        )
        extra: dict = {}
        if cfg.provider == AIProvider.openrouter:
            if cfg.site_url:  extra["HTTP-Referer"] = cfg.site_url
            if cfg.site_name: extra["X-Title"] = cfg.site_name

        resp = await client.messages.create(
            model=cfg.model,
            max_tokens=50,
            messages=[{"role": "user", "content": "Responda apenas: OK"}],
            **({"extra_headers": extra} if extra else {}),
        )
        reply = resp.content[0].text if resp.content else ""
        return {
            "success": True,
            "provider": cfg.provider,
            "model": cfg.model,
            "response": reply,
            "input_tokens":  resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
    except Exception as e:
        import re as _re
        err_raw = str(e)

        # Strip HTML from error message (CDN/WAF pages, CloudFlare, etc.)
        err_clean = _re.sub(r"<[^>]+>", " ", err_raw)  # remove HTML tags
        err_clean = _re.sub(r"\s{2,}", " ", err_clean).strip()  # collapse whitespace
        err_clean = err_clean[:300]  # cap length

        # Extract HTTP status code if present
        status_match = _re.search(r"\b(\d{3})\b", err_raw)
        status_code   = status_match.group(1) if status_match else ""

        # Give actionable diagnosis
        if status_code in ("401", "403") or "authentication" in err_raw.lower() or "invalid_api_key" in err_raw:
            hint = "API key inválida ou sem permissão para este modelo."
            short = f"HTTP {status_code} — API key inválida"
        elif status_code in ("402",):
            hint = "Saldo insuficiente no OpenRouter. Adicione créditos em openrouter.ai."
            short = "HTTP 402 — sem saldo"
        elif status_code in ("404",) or "not_found" in err_raw or "no endpoints" in err_raw.lower():
            hint = f"Modelo '{cfg.model}' não encontrado ou indisponível neste provedor."
            short = f"HTTP 404 — modelo não encontrado"
        elif status_code in ("429",) or "quota" in err_raw.lower() or "rate_limit" in err_raw:
            hint = "Limite de requisições atingido. Aguarde e tente novamente."
            short = "HTTP 429 — rate limit"
        elif status_code in ("500", "502", "503", "504"):
            hint = f"Erro no servidor do provedor (HTTP {status_code}). Tente novamente em instantes."
            short = f"HTTP {status_code} — erro no servidor"
        elif "timeout" in err_raw.lower() or "Timeout" in type(e).__name__:
            if is_openrouter:
                hint = "Proxy/firewall bloqueando openrouter.ai. Verifique se ANTHROPIC_SSL_VERIFY=false está no .env e reinicie o backend."
                short = "Timeout — possível bloqueio de proxy SSL corporativo"
            else:
                hint = "Proxy/firewall bloqueando api.anthropic.com. Verifique se ANTHROPIC_SSL_VERIFY=false está no .env."
                short = "Timeout — possível bloqueio de proxy SSL corporativo"
        elif "SSL" in err_raw or "certificate" in err_raw.lower() or "CERTIFICATE" in err_raw:
            hint = "Erro SSL. Adicione OPENROUTER_SSL_VERIFY=false no .env (proxy corporativo)."
            short = "Erro de certificado SSL"
        elif "connect" in err_raw.lower() or "ConnectError" in type(e).__name__:
            hint = "Não foi possível conectar. Proxy/firewall bloqueando? Adicione SSL_VERIFY=false no .env."
            short = "Erro de conexão"
        else:
            hint = "Verifique API key, ID do modelo e configurações de rede no painel admin."
            short = err_clean[:120]

        return {
            "success":    False,
            "error":      short,          # short clean message for display
            "error_type": type(e).__name__,
            "hint":       hint,
            "provider":   cfg.provider,
            "model":      cfg.model,
        }


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
