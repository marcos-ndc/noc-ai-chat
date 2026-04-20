"""
AIConfigStore: gerencia configuração de IA em runtime.
Persiste no Redis para sobreviver a restarts do backend.
Fallback para settings.py se Redis não disponível.
"""
import json
from typing import Optional
import structlog

from app.models import AIConfig, AIProvider
from app.settings import settings

log = structlog.get_logger()

_REDIS_KEY = "admin:ai_config"


class AIConfigStore:
    """Thread-safe config store backed by Redis with in-memory cache."""

    def __init__(self):
        self._cache: Optional[AIConfig] = None

    def _default(self) -> AIConfig:
        """Build default config from .env settings."""
        return AIConfig(
            provider=AIProvider.anthropic,
            model=settings.claude_model,
            api_key=settings.anthropic_api_key,
        )

    async def get(self) -> AIConfig:
        if self._cache:
            return self._cache

        try:
            from app.agent.session import session_manager
            raw = await session_manager.redis.get(_REDIS_KEY)
            if raw:
                data = json.loads(raw)
                cfg = AIConfig(**data)
                self._cache = cfg
                return cfg
        except Exception as e:
            log.warning("ai_config.redis_read_error", error=str(e))

        cfg = self._default()
        self._cache = cfg
        return cfg

    async def save(self, cfg: AIConfig) -> None:
        self._cache = cfg
        try:
            from app.agent.session import session_manager
            await session_manager.redis.set(
                _REDIS_KEY,
                json.dumps(cfg.model_dump()),
                ex=86400 * 365,   # 1 year TTL
            )
            log.info("ai_config.saved", provider=cfg.provider, model=cfg.model)
        except Exception as e:
            log.warning("ai_config.redis_write_error", error=str(e))

    def invalidate_cache(self) -> None:
        self._cache = None


ai_config_store = AIConfigStore()
