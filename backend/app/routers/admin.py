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
        import anthropic as _anthropic
        client = orchestrator._build_client(
            api_key,
            cfg.openrouter_base_url if is_openrouter else None,
        )
        extra: dict = {}
        if is_openrouter:
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

    except _anthropic.NotFoundError:
        return {
            "success": False,
            "error": f"Modelo '{cfg.model}' não encontrado no {cfg.provider}.",
            "error_type": "NotFoundError",
            "hint": (
                "Verifique se o ID do modelo está correto. "
                "Exemplos válidos para OpenRouter: 'anthropic/claude-sonnet-4-5', "
                "'openai/gpt-4o', 'meta-llama/llama-3.3-70b-instruct'."
            ),
            "provider": cfg.provider,
            "model": cfg.model,
        }

    except _anthropic.AuthenticationError:
        return {
            "success": False,
            "error": "API key inválida ou expirada.",
            "error_type": "AuthenticationError",
            "hint": (
                "Verifique a chave no campo API Key. "
                + ("Chaves OpenRouter começam com 'sk-or-v1-'. Gere uma nova em openrouter.ai/keys."
                   if is_openrouter else
                   "Chaves Anthropic começam com 'sk-ant-'. Verifique em console.anthropic.com.")
            ),
            "provider": cfg.provider,
            "model": cfg.model,
        }

    except _anthropic.PermissionDeniedError:
        return {
            "success": False,
            "error": "Sem permissão para usar este modelo.",
            "error_type": "PermissionDeniedError",
            "hint": (
                "Sua conta pode não ter acesso a este modelo. "
                + ("Verifique se tem créditos no OpenRouter (openrouter.ai/activity)."
                   if is_openrouter else
                   "Verifique os limites do seu plano Anthropic.")
            ),
            "provider": cfg.provider,
            "model": cfg.model,
        }

    except _anthropic.RateLimitError:
        return {
            "success": False,
            "error": "Limite de requisições atingido.",
            "error_type": "RateLimitError",
            "hint": "Aguarde alguns segundos e tente novamente. Se persistir, verifique seu saldo.",
            "provider": cfg.provider,
            "model": cfg.model,
        }

    except _anthropic.APITimeoutError:
        return {
            "success": False,
            "error": "Timeout — proxy SSL corporativo provavelmente bloqueando a conexão.",
            "error_type": "APITimeoutError",
            "hint": (
                "Em ambientes corporativos o firewall bloqueia conexões HTTPS externas. "
                "Confirme que ANTHROPIC_SSL_VERIFY=false está no .env e reinicie o backend com 'make dev'."
            ),
            "provider": cfg.provider,
            "model": cfg.model,
        }

    except _anthropic.APIConnectionError as e:
        return {
            "success": False,
            "error": f"Não foi possível conectar: {str(e)[:120]}",
            "error_type": "APIConnectionError",
            "hint": (
                "Proxy/firewall bloqueando a conexão. "
                "Confirme que ANTHROPIC_SSL_VERIFY=false está no .env e reinicie o backend."
            ),
            "provider": cfg.provider,
            "model": cfg.model,
        }

    except Exception as e:
        import re as _re
        err_raw = str(e)
        err_clean = _re.sub(r"<[^>]+>", " ", err_raw)
        err_clean = _re.sub(r"\s{2,}", " ", err_clean).strip()[:200]
        return {
            "success":    False,
            "error":      err_clean,
            "error_type": type(e).__name__,
            "hint":       "Verifique API key, ID do modelo e configurações de rede.",
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
