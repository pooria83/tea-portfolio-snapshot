import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.api.v1.chat_deps import get_chat_service
from app.core.config import settings
from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.error_codes import E
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ServiceUnavailableError
from app.core.jwt import decode_token, extract_bearer_token
from app.core.logging import log_source_var, request_id_var, user_id_var
from app.schemas.chat import message_from_doc
from app.services.chat_service import ChatService

router = APIRouter(tags=["websocket"])

_MAX_WS_MESSAGE_SIZE = 1024 * 10


async def _authenticate_ws(websocket: WebSocket) -> tuple[str, str | None]:
    token = ""
    subprotocol: str | None = None
    requested = websocket.headers.get("sec-websocket-protocol", "")
    if requested:
        candidate = requested.split(",")[0].strip()
        if candidate:
            token = candidate
            subprotocol = candidate
    if not token:
        token = websocket.cookies.get(ACCESS_TOKEN_COOKIE, "")
    if not token:
        token = websocket.query_params.get("token", "")
    if not token:
        token = extract_bearer_token(websocket.headers.get("authorization")) or ""
    if token:
        try:
            payload = decode_token(token)
            user_id_var.set(payload.sub)
            log_source_var.set("authenticated")
            request_id_var.set(f"ws_{payload.sub}")
            return payload.sub, subprotocol
        except AuthenticationError:
            pass
    raise AuthenticationError("WebSocket authentication required", translation_key=E.WEBSOCKET_AUTH_REQUIRED)


async def _relay_chat_stream(
    service: ChatService,
    websocket: WebSocket,
    user_id: str,
    conversation_id: str,
    content: str,
    idempotency_key: str,
    include_saved_message: bool,
) -> str | None:
    """Relay engine frames over the socket using the shared stream generator,
    persisting the user turn and the final assistant message in the service.
    The generator emits the ``message_saved`` frame itself (with the saved
    assistant and user messages when requested)."""
    stream = service.send_message_stream(
        user_id=user_id,
        conversation_id=conversation_id,
        content=content,
        idempotency_key=idempotency_key,
        request_id=request_id_var.get() or "",
        include_saved_message=include_saved_message,
    )
    saved_message_id: str | None = None
    try:
        async for frame in stream:
            if frame.get("type") == "message_saved":
                message_id = frame.get("message_id")
                saved_message_id = str(message_id) if message_id else None
            await websocket.send_json(frame)
    except WebSocketDisconnect:
        logger.info("ws_chat_disconnected user_id={} conversation_id={}", user_id, conversation_id)
        return None
    except NotFoundError:
        await websocket.send_json({"type": "error", "code": "conversation_not_found"})
        return None
    except ConflictError:
        code = "conversation_closed"
        try:
            doc = await service.conversations.find_by_id_and_user(conversation_id, user_id)
            if doc and int(doc.get("userMessageCount", 0)) >= settings.chat_max_messages:
                code = "chat_limit_reached"
        except Exception:
            pass
        await websocket.send_json({"type": "error", "code": code})
        return None
    except Exception:
        logger.exception("ws_chat_engine_failed user_id={} conversation_id={}", user_id, conversation_id)
        await websocket.send_json({"type": "error", "code": "chat_failed"})
        return None
    return saved_message_id


async def _chat_websocket_handler(websocket: WebSocket, conversation_id: str) -> None:
    try:
        user_id, subprotocol = await _authenticate_ws(websocket)
    except AuthenticationError:
        await websocket.close(code=4001)
        return
    try:
        service = get_chat_service(websocket.app)
    except ServiceUnavailableError:
        service = None
    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if len(data) > _MAX_WS_MESSAGE_SIZE:
                await websocket.send_json({"type": "error", "code": "message_too_large", "message": "Message too large"})
                continue
            try:
                frame = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "code": "invalid_frame", "message": "Invalid frame"})
                continue
            if frame.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if frame.get("type") == "similar_request":
                if service is None:
                    await websocket.send_json({"type": "error", "code": "chat_not_available"})
                    continue
                product_id = str(frame.get("product_id", "")).strip()
                if not product_id:
                    await websocket.send_json({"type": "error", "code": "missing_product_id", "message": "Missing product_id"})
                    continue
                product_name = str(frame.get("product_name", "")).strip()
                try:
                    similar_message = await service.find_similar(
                        conversation_id,
                        user_id,
                        product_id,
                        request_id=request_id_var.get() or "",
                        product_name=product_name,
                    )
                except NotFoundError:
                    await websocket.send_json({"type": "error", "code": "product_not_found"})
                    continue
                except ConflictError:
                    await websocket.send_json({"type": "error", "code": "conversation_closed"})
                    continue
                except Exception:
                    logger.exception("ws_chat_similar_failed user_id={} conversation_id={} product_id={}", user_id, conversation_id, product_id)
                    await websocket.send_json({"type": "error", "code": "chat_failed"})
                    continue
                snapshots = [p for p in (similar_message.get("productSnapshots") or []) if isinstance(p, dict)]
                await websocket.send_json(
                    {
                        "type": "product_cards",
                        "products": snapshots,
                        "locale": similar_message.get("locale"),
                    }
                )
                await websocket.send_json({"type": "assistant_end"})
                similar_saved: dict[str, Any] = {"type": "message_saved", "conversation_id": conversation_id}
                if frame.get("include_saved_message") is True:
                    try:
                        doc = await service.messages.find_by_id(str(similar_message.get("_id", "")), conversation_id)
                        if doc:
                            similar_saved["message"] = message_from_doc(doc).model_dump(mode="json")
                        similar_saved["user_message"] = None
                    except Exception:
                        logger.exception("ws_chat_saved_lookup_failed")
                await websocket.send_json(similar_saved)
                continue
            if frame.get("type") != "send_message":
                await websocket.send_json({"type": "error", "code": "unsupported_frame", "message": "Unsupported frame"})
                continue
            if service is None:
                await websocket.send_json({"type": "error", "code": "chat_not_available"})
                continue
            content = str(frame.get("content", "")).strip()
            if not content:
                await websocket.send_json({"type": "error", "code": "empty_content", "message": "Empty content"})
                continue
            idempotency_key = str(frame.get("idempotency_key", ""))
            await _relay_chat_stream(
                service,
                websocket,
                user_id,
                conversation_id,
                content,
                idempotency_key,
                include_saved_message=frame.get("include_saved_message") is True,
            )
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/chat/{conversation_id}")
async def chat_stream_websocket(websocket: WebSocket, conversation_id: str) -> None:
    await _chat_websocket_handler(websocket, conversation_id)
