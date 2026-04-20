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

    try:
        client = orchestrator._build_client(
            api_key,
            cfg.openrouter_base_url if cfg.provider == AIProvider.openrouter else None,
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
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


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
