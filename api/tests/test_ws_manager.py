from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.websockets import WebSocketState

from app.services.ws_manager import ConnectionManager


@pytest.fixture
def manager() -> ConnectionManager:
    return ConnectionManager()


@pytest.fixture
def mock_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    return ws


@pytest.mark.asyncio
async def test_connect_adds_connection(manager: ConnectionManager, mock_ws: AsyncMock):
    await manager.connect("user-1", mock_ws)
    assert "user-1" in manager.active
    assert mock_ws in manager.active["user-1"]
    mock_ws.accept.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_multiple_for_same_user(manager: ConnectionManager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect("user-1", ws1)
    await manager.connect("user-1", ws2)
    assert len(manager.active["user-1"]) == 2


def test_disconnect_removes_single_connection(manager: ConnectionManager):
    ws1 = MagicMock()
    ws2 = MagicMock()
    manager.active = {"user-1": [ws1, ws2]}
    manager.disconnect("user-1", ws1)
    assert ws1 not in manager.active["user-1"]
    assert ws2 in manager.active["user-1"]


def test_disconnect_removes_user_when_empty(manager: ConnectionManager):
    ws = MagicMock()
    manager.active = {"user-1": [ws]}
    manager.disconnect("user-1", ws)
    assert "user-1" not in manager.active


def test_disconnect_unknown_user(manager: ConnectionManager):
    manager.disconnect("nonexistent", MagicMock())
    assert not manager.active


@pytest.mark.asyncio
async def test_send_to_user_sends_to_live_connections(manager: ConnectionManager, mock_ws: AsyncMock):
    manager.active = {"user-1": [mock_ws]}
    await manager.send_to_user("user-1", {"type": "test"})
    mock_ws.send_json.assert_awaited_once_with({"type": "test"})


@pytest.mark.asyncio
async def test_send_to_user_skips_disconnected(manager: ConnectionManager):
    live_ws = AsyncMock()
    live_ws.client_state = WebSocketState.CONNECTED
    dead_ws = AsyncMock()
    dead_ws.client_state = WebSocketState.DISCONNECTED
    manager.active = {"user-1": [live_ws, dead_ws]}
    await manager.send_to_user("user-1", {"type": "test"})
    live_ws.send_json.assert_awaited_once()
    dead_ws.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_to_user_handles_disconnect_during_send(manager: ConnectionManager):
    from fastapi import WebSocketDisconnect

    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    ws.send_json.side_effect = WebSocketDisconnect(code=1000)
    manager.active = {"user-1": [ws]}
    await manager.send_to_user("user-1", {"type": "test"})
    assert "user-1" not in manager.active


@pytest.mark.asyncio
async def test_send_to_user_cleans_up_stale_connections(manager: ConnectionManager):
    stale_ws = AsyncMock()
    stale_ws.client_state = WebSocketState.DISCONNECTED
    manager.active = {"user-1": [stale_ws]}
    await manager.send_to_user("user-1", {"type": "test"})
    assert "user-1" not in manager.active


@pytest.mark.asyncio
async def test_send_to_user_does_not_requeue_failed_socket(manager: ConnectionManager):
    from fastapi import WebSocketDisconnect

    ok_ws = AsyncMock()
    ok_ws.client_state = WebSocketState.CONNECTED
    bad_ws = AsyncMock()
    bad_ws.client_state = WebSocketState.CONNECTED
    bad_ws.send_json.side_effect = WebSocketDisconnect(code=1001)
    manager.active = {"user-1": [ok_ws, bad_ws]}
    await manager.send_to_user("user-1", {"type": "test"})
    assert manager.active["user-1"] == [ok_ws]


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_users(manager: ConnectionManager):
    ws1 = AsyncMock()
    ws1.client_state = WebSocketState.CONNECTED
    ws2 = AsyncMock()
    ws2.client_state = WebSocketState.CONNECTED
    manager.active = {"user-1": [ws1], "user-2": [ws2]}
    await manager.broadcast({"type": "broadcast"})
    ws1.send_json.assert_awaited_once_with({"type": "broadcast"})
    ws2.send_json.assert_awaited_once_with({"type": "broadcast"})


@pytest.mark.asyncio
async def test_close_closes_all_and_clears(manager: ConnectionManager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    manager.active = {"user-1": [ws1], "user-2": [ws2]}
    await manager.close()
    ws1.close.assert_awaited_once_with(code=1001)
    ws2.close.assert_awaited_once_with(code=1001)
    assert manager.active == {}


@pytest.mark.asyncio
async def test_close_tolerates_failing_socket(manager: ConnectionManager):
    ws = AsyncMock()
    ws.close.side_effect = RuntimeError("already closed")
    manager.active = {"user-1": [ws]}
    await manager.close()
    assert manager.active == {}


@pytest.mark.asyncio
async def test_close_on_empty_manager(manager: ConnectionManager):
    await manager.close()
    assert manager.active == {}
