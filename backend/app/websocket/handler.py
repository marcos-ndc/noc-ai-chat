import json
import uuid
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect, status

from app.agent.orchestrator import orchestrator
from app.agent.session import session_manager
from app.auth.service import auth_service
from app.models import (
    ChatMessage, MessageRole,
    SessionData, UserOut,
    WSEventType, WSInbound, WSOutbound,
)
import structlog

log = structlog.get_logger()


class ConnectionManager:
    """Tracks active WebSocket connections."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[session_id] = ws
        log.info("ws.connected", session_id=session_id, total=len(self._connections))

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)
        log.info("ws.disconnected", session_id=session_id, total=len(self._connections))

    async def send(self, session_id: str, event: WSOutbound) -> None:
        ws = self._connections.get(session_id)
        if ws:
            await ws.send_text(event.to_json())

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


async def authenticate_websocket(ws: WebSocket) -> Optional[UserOut]:
    """Extract and validate JWT from query param ?token="""
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token ausente")
        return None

    user = auth_service.get_user_from_token(token)
    if not user:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
        return None

    return user


async def get_or_create_session(session_id: str, user: UserOut) -> SessionData:
    session = await session_manager.get_session(session_id)
    if not session:
        session = SessionData(
            session_id=session_id,
            user_id=user.id,
            user_profile=user.profile,
        )
        await session_manager.save_session(session)
    return session


async def handle_chat_websocket(ws: WebSocket) -> None:
    """Main WebSocket handler for /ws/chat"""
    user = await authenticate_websocket(ws)
    if not user:
        return

    connection_id = str(uuid.uuid4())[:8]
    await manager.connect(connection_id, ws)

    try:
        while True:
            raw = await ws.receive_text()

            try:
                data = json.loads(raw)
                inbound = WSInbound(**data)
            except Exception:
                await manager.send(connection_id, WSOutbound(
                    type=WSEventType.error,
                    error="Formato de mensagem inválido",
                ))
                continue

            if inbound.type == WSEventType.ping:
                await manager.send(connection_id, WSOutbound(type=WSEventType.pong))
                continue

            if inbound.type != WSEventType.user_message or not inbound.content:
                continue

            # Resolve session
            session_id = inbound.sessionId or connection_id
            session = await get_or_create_session(session_id, user)

            log.info(
                "ws.message_received",
                session_id=session_id,
                user_id=user.id,
                content_length=len(inbound.content),
            )

            # Stream agent response
            try:
                async for event in orchestrator.process_message(
                    user_message=inbound.content,
                    session=session,
                ):
                    await manager.send(connection_id, event)

            except Exception as e:
                log.error("ws.agent_error", error=str(e), session_id=session_id)
                await manager.send(connection_id, WSOutbound(
                    type=WSEventType.error,
                    error="Erro interno ao processar sua mensagem. Tente novamente.",
                ))

    except WebSocketDisconnect:
        log.info("ws.client_disconnected", connection_id=connection_id)
    except Exception as e:
        log.error("ws.unexpected_error", error=str(e), connection_id=connection_id)
    finally:
        manager.disconnect(connection_id)
