import contextlib
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        if user_id in self.active:
            self.active[user_id] = [w for w in self.active[user_id] if w is not ws]
            if not self.active[user_id]:
                del self.active[user_id]

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        if user_id not in self.active:
            return
        live = [ws for ws in self.active[user_id] if ws.client_state == WebSocketState.CONNECTED]
        remaining: list[WebSocket] = []
        for ws in live:
            try:
                await ws.send_json(message)
                remaining.append(ws)
            except Exception:
                pass
        self.active[user_id] = remaining
        if not remaining:
            del self.active[user_id]

    async def broadcast(self, message: dict[str, Any]) -> None:
        for user_id in list(self.active):
            await self.send_to_user(user_id, message)

    async def close(self) -> None:
        """Gracefully close every tracked connection and clear the registry.

        Called during shutdown so sockets are terminated before the event
        loop stops instead of leaking open.
        """
        for user_id in list(self.active):
            for ws in self.active[user_id]:
                with contextlib.suppress(Exception):
                    await ws.close(code=1001)
        self.active.clear()
