import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models import ChatMessage, MessageRole, SessionData, UserProfile


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def session_manager(mock_redis):
    from app.agent.session import SessionManager
    return SessionManager(redis=mock_redis)


@pytest.mark.asyncio
class TestSessionManager:

    async def test_get_session_returns_none_when_not_found(self, session_manager, mock_redis):
        mock_redis.get.return_value = None
        result = await session_manager.get_session("non-existent")
        assert result is None

    async def test_save_and_get_session_roundtrip(self, session_manager, mock_redis):
        session = SessionData(
            session_id="sess-1",
            user_id="user-1",
            user_profile=UserProfile.N1,
        )
        # Simulate save then get
        saved_json = session.model_dump_json()
        mock_redis.get.return_value = saved_json

        await session_manager.save_session(session)
        result = await session_manager.get_session("sess-1")

        assert result is not None
        assert result.session_id == "sess-1"
        assert result.user_profile == UserProfile.N1

    async def test_append_message_adds_to_history(self, session_manager, mock_redis):
        session = SessionData(
            session_id="sess-1",
            user_id="user-1",
            user_profile=UserProfile.N2,
        )
        mock_redis.get.return_value = session.model_dump_json()

        msg = ChatMessage(role=MessageRole.user, content="Tem alertas críticos?")
        await session_manager.append_message("sess-1", msg)

        # Verify redis.set was called with updated session
        assert mock_redis.set.called
        call_args = mock_redis.set.call_args
        import json
        saved = json.loads(call_args[0][1])
        assert len(saved["messages"]) == 1
        assert saved["messages"][0]["content"] == "Tem alertas críticos?"

    async def test_session_saved_with_ttl(self, session_manager, mock_redis):
        session = SessionData(
            session_id="sess-1",
            user_id="user-1",
            user_profile=UserProfile.engineer,
        )
        await session_manager.save_session(session)

        call_kwargs = mock_redis.set.call_args[1]
        assert "ex" in call_kwargs or "px" in call_kwargs  # TTL set

    async def test_history_trimmed_at_max_turns(self, session_manager, mock_redis):
        from app.settings import settings
        messages = [
            ChatMessage(role=MessageRole.user, content=f"msg {i}")
            for i in range(settings.max_history_turns + 10)
        ]
        session = SessionData(
            session_id="sess-1",
            user_id="user-1",
            user_profile=UserProfile.N1,
            messages=messages,
        )
        trimmed = session_manager.trim_history(session)
        assert len(trimmed.messages) <= settings.max_history_turns

    async def test_delete_session(self, session_manager, mock_redis):
        await session_manager.delete_session("sess-1")
        mock_redis.delete.assert_called_once()
