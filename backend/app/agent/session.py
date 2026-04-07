from typing import Optional
import redis.asyncio as aioredis

from app.models import ChatMessage, MessageRole, SessionData
from app.settings import settings


class SessionManager:
    def __init__(self, redis: Optional[aioredis.Redis] = None):
        self._redis = redis

    @property
    def redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    @redis.setter
    def redis(self, value: aioredis.Redis) -> None:
        self._redis = value

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        raw = await self.redis.get(self._key(session_id))
        if not raw:
            return None
        return SessionData.model_validate_json(raw)

    async def save_session(self, session: SessionData) -> None:
        await self.redis.set(
            self._key(session.session_id),
            session.model_dump_json(),
            ex=settings.session_ttl_seconds,
        )

    async def append_message(self, session_id: str, message: ChatMessage) -> SessionData:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        session.messages.append(message)
        session = self.trim_history(session)
        await self.save_session(session)
        return session

    def trim_history(self, session: SessionData) -> SessionData:
        max_turns = settings.max_history_turns
        if len(session.messages) > max_turns:
            # Keep system context: trim oldest, preserve last N turns
            session.messages = session.messages[-max_turns:]
        return session

    async def delete_session(self, session_id: str) -> None:
        await self.redis.delete(self._key(session_id))

    def build_claude_messages(self, session: SessionData) -> list[dict]:
        """Convert session messages to Claude API format."""
        return [
            {"role": msg.role.value if msg.role != "agent" else "assistant",
             "content": msg.content}
            for msg in session.messages
        ]


session_manager = SessionManager()
