import pytest
from fastapi import WebSocketDisconnect

from app.core.jwt import create_access_token
from app.main import app
from app.services.ws_manager import ConnectionManager


def _make_client():
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")
        from starlette.testclient import TestClient

        return TestClient(app, backend="asyncio")


def test_chat_websocket_no_auth():
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/v1/ws/chat/conv-1"):
        pass


def test_chat_websocket_invalid_frame():
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect(f"/api/v1/ws/chat/conv-1?token={token}") as ws:
        ws.send_text("hello")
        response = ws.receive_json()
        assert response == {"type": "error", "code": "invalid_frame", "message": "Invalid frame"}


def test_chat_stream_websocket_ping_pong():
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect(f"/api/v1/ws/chat/conv-1?token={token}") as ws:
        ws.send_text('{"type": "ping"}')
        response = ws.receive_json()
        assert response == {"type": "pong"}


def test_chat_websocket_subprotocol_auth_echoes_protocol():
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect("/api/v1/ws/chat/conv-1", subprotocols=[token]) as ws:
        assert ws.accepted_subprotocol == token
        ws.send_text('{"type": "ping"}')
        response = ws.receive_json()
        assert response == {"type": "pong"}


def test_chat_websocket_cookie_auth():
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    client.cookies.set("access_token", token)
    with client.websocket_connect("/api/v1/ws/chat/conv-1") as ws:
        ws.send_text('{"type": "ping"}')
        response = ws.receive_json()
        assert response == {"type": "pong"}
