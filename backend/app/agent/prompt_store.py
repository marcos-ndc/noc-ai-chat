"""
PromptStore: gerencia overrides de system prompts em runtime.
Persiste no Redis. Sem override → prompts hardcoded em prompt.py são usados.
"""
import structlog
from typing import Optional

log = structlog.get_logger()

_REDIS_PREFIX = "admin:prompt:"


class PromptStore:
    """Redis-backed store for admin-overridable system prompt texts."""

    async def get_override(self, key: str) -> Optional[str]:
        try:
            from app.agent.session import session_manager
            raw = await session_manager.redis.get(f"{_REDIS_PREFIX}{key}")
            if raw:
                return raw.decode() if isinstance(raw, bytes) else str(raw)
        except Exception as e:
            log.warning("prompt_store.redis_read_error", key=key, error=str(e))
        return None

    async def set_override(self, key: str, text: str) -> None:
        try:
            from app.agent.session import session_manager
            await session_manager.redis.set(
                f"{_REDIS_PREFIX}{key}", text.encode(), ex=86400 * 365
            )
            log.info("prompt_store.saved", key=key)
        except Exception as e:
            log.warning("prompt_store.redis_write_error", key=key, error=str(e))

    async def clear_override(self, key: str) -> None:
        try:
            from app.agent.session import session_manager
            await session_manager.redis.delete(f"{_REDIS_PREFIX}{key}")
            log.info("prompt_store.cleared", key=key)
        except Exception as e:
            log.warning("prompt_store.redis_delete_error", key=key, error=str(e))


prompt_store = PromptStore()
