from unittest.mock import AsyncMock, patch

import pytest

from app.core.broker import Broker


@pytest.fixture
def mock_conn_and_channel():
    conn = AsyncMock()
    conn.is_closed = False
    channel = AsyncMock()
    conn.channel = AsyncMock(return_value=channel)
    return conn, channel


class TestBroker:
    @pytest.mark.asyncio
    async def test_init_broker_connects_and_declares_queues(self, mock_conn_and_channel):
        conn, channel = mock_conn_and_channel
        with patch("app.core.broker.aio_pika.connect_robust", new_callable=AsyncMock, return_value=conn):
            from app.core.broker import init_broker

            broker = await init_broker()
            assert isinstance(broker, Broker)
            channel.declare_queue.assert_any_call("search_requests", durable=True)
            channel.declare_queue.assert_any_call("web_scrape_jobs", durable=True)

    @pytest.mark.asyncio
    async def test_is_connected(self, mock_conn_and_channel):
        conn, channel = mock_conn_and_channel
        broker = Broker(conn, channel)
        assert broker.is_connected() is True

    @pytest.mark.asyncio
    async def test_is_not_connected_when_closed(self):
        conn = AsyncMock()
        conn.is_closed = True
        broker = Broker(conn, AsyncMock())
        assert broker.is_connected() is False

    @pytest.mark.asyncio
    async def test_publish_event(self, mock_conn_and_channel):
        conn, channel = mock_conn_and_channel
        broker = Broker(conn, channel)
        await broker.publish_event("test_queue", {"key": "value"})
        channel.default_exchange.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_closes_channel_and_connection(self, mock_conn_and_channel):
        conn, channel = mock_conn_and_channel
        broker = Broker(conn, channel)
        await broker.close()
        channel.close.assert_called_once()
        conn.close.assert_called_once()
