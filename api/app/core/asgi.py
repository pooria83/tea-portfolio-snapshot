from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

OnResponseStart = Callable[[MutableMapping[str, Any]], None]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
SendWrapper = Callable[[MutableMapping[str, Any]], Awaitable[None]]


def wrap_send(send: Send, on_start: OnResponseStart) -> SendWrapper:
    async def wrapper(message: MutableMapping[str, Any]) -> None:
        if message["type"] == "http.response.start":
            on_start(message)
        await send(message)

    return wrapper
