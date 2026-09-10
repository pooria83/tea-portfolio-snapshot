import json
from typing import Any

import aio_pika

from app.core.config import settings


class Broker:
    def __init__(self, connection: aio_pika.abc.AbstractConnection, channel: aio_pika.abc.AbstractChannel) -> None:
        self.connection = connection
        self.channel = channel

    def is_connected(self) -> bool:
        return self.connection is not None and not self.connection.is_closed

    async def publish_event(self, queue_name: str, payload: dict[str, Any]) -> None:
        message = aio_pika.Message(
            body=json.dumps(payload, default=str).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.channel.default_exchange.publish(message, routing_key=queue_name)

    async def close(self) -> None:
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()


async def init_broker() -> Broker:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url, timeout=30)
    channel = await connection.channel()
    await channel.declare_queue("search_requests", durable=True)
    await channel.declare_queue("web_scrape_jobs", durable=True)
    return Broker(connection, channel)
