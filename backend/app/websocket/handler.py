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

            # Manual specialist selection
            if inbound.specialist and inbound.specialist != session.active_specialist:
                from app.models import Specialist as _Spec
                if inbound.specialist in [s.value for s in _Spec]:
                    session.active_specialist = inbound.specialist
                    await session_manager.save_session(session)

            log.info(
                "ws.message_received",
                session_id=session_id,
                user_id=user.id,
                content_length=len(inbound.content),
                voice_mode=inbound.voiceMode,
                specialist=session.active_specialist,
            )

            # Stream agent response
            try:
                async for event in orchestrator.process_message(
                    user_message=inbound.content,
                    session=session,
                    voice_mode=inbound.voiceMode,
                ):
                    await manager.send(connection_id, event)

            except Exception as e:
                import traceback
                error_type = type(e).__name__
                error_detail = str(e)
                tb = traceback.format_exc()
                log.error("ws.agent_error",
                    error=error_detail,
                    error_type=error_type,
                    traceback=tb,
                    session_id=session_id,
                )
                # Build user-friendly message based on error type
                # Detect provider from config for better messages
                try:
                    from app.agent.ai_config import ai_config_store
                    _cfg = await ai_config_store.get()
                    _provider = _cfg.provider.value
                    _model    = _cfg.model
                except Exception:
                    _provider = "anthropic"
                    _model    = "?"

                provider_label = f"{_provider} ({_model})"
                # Strip HTML tags from error (CDN/WAF error pages)
                import re as _re
                error_clean = _re.sub(r"<[^>]+>", " ", error_detail)
                error_clean = _re.sub(r"\s{2,}", " ", error_clean).strip()[:200]
                error_msg = error_clean

                if "401" in error_detail or "403" in error_detail or "authentication" in error_detail.lower() or "API_KEY" in error_detail:
                    error_msg = f"⚠️ API key inválida para {_provider}. Verifique a chave no painel /admin."
                elif "SSL" in error_msg or "certificate" in error_msg.lower() or "CERTIFICATE" in error_msg:
                    error_msg = f"⚠️ Erro SSL ao conectar em {_provider}. Adicione SSL_VERIFY=false no .env (proxy corporativo)."
                elif "timeout" in error_msg.lower() or "Timeout" in error_type or "ReadTimeout" in error_type:
                    error_msg = f"⚠️ Timeout ao chamar {provider_label}. O modelo pode estar sobrecarregado. Tente novamente ou escolha outro modelo no painel /admin."
                elif "Connection" in error_msg or "ConnectError" in error_type or "connect" in error_msg.lower():
                    error_msg = f"⚠️ Não foi possível conectar a {_provider}. Verifique se o proxy/firewall permite acesso. Detalhe: {error_detail[:120]}"
                elif "not_found" in error_msg or "404" in error_msg or "model" in error_msg.lower():
                    error_msg = f"⚠️ Modelo '{_model}' não encontrado em {_provider}. Verifique o ID do modelo no painel /admin."
                elif "insufficient_quota" in error_msg or "quota" in error_msg.lower() or "429" in error_msg:
                    error_msg = f"⚠️ Limite de uso atingido em {_provider}. Verifique seu saldo/cota."
                else:
                    error_msg = f"⚠️ Erro em {provider_label}: {error_detail[:200]}"
                await manager.send(connection_id, WSOutbound(
                    type=WSEventType.error,
                    error=error_msg,
                ))

    except WebSocketDisconnect:
        log.info("ws.client_disconnected", connection_id=connection_id)
    except Exception as e:
        log.error("ws.unexpected_error", error=str(e), connection_id=connection_id)
    finally:
        manager.disconnect(connection_id)
