import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from app.core.broker import Broker
from app.main import _shutdown_event
from app.services.ws_manager import ConnectionManager


@pytest.fixture
def isolated_app() -> FastAPI:
    app = FastAPI()
    app.state.ai_client = AsyncMock()
    app.state.broker = AsyncMock(spec=Broker)
    app.state.ws_manager = ConnectionManager()
    return app


@pytest.fixture(autouse=True)
def reset_shutdown_event():
    yield
    _shutdown_event.clear()


@pytest.mark.asyncio
async def test_shutdown_cancels_tasks(isolated_app: FastAPI):
    task = asyncio.create_task(asyncio.sleep(100))
    isolated_app.state.product_ai_cron = task

    from app.main import _shutdown

    await _shutdown(isolated_app)
    assert task.cancelled()


@pytest.mark.asyncio
async def test_shutdown_closes_ws_manager(isolated_app: FastAPI):
    ws_manager = ConnectionManager()
    isolated_app.state.ws_manager = ws_manager

    from app.main import _shutdown

    await _shutdown(isolated_app)
    assert ws_manager.active == {}


@pytest.mark.asyncio
async def test_shutdown_closes_redis_and_engine(isolated_app: FastAPI):
    isolated_app.state.redis = AsyncMock()
    isolated_app.state.engine = AsyncMock()

    from app.main import _shutdown

    await _shutdown(isolated_app)
    isolated_app.state.redis.aclose.assert_awaited_once()
    isolated_app.state.engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_without_broker():
    test_app = FastAPI()
    test_app.state.ai_client = AsyncMock()
    test_app.state.broker = None
    test_app.state.ws_manager = ConnectionManager()

    from app.main import _shutdown

    await _shutdown(test_app)


@pytest.mark.asyncio
async def test_shutdown_without_redis():
    test_app = FastAPI()
    test_app.state.ai_client = AsyncMock()
    test_app.state.broker = AsyncMock(spec=Broker)
    test_app.state.ws_manager = ConnectionManager()

    from app.main import _shutdown

    await _shutdown(test_app)


@pytest.mark.asyncio
async def test_startup_sets_up_state():
    test_app = FastAPI()

    with (
        patch("app.main.setup_logging"),
        patch("app.main.from_url", AsyncMock(return_value=AsyncMock())),
        patch("app.main.create_async_engine") as mock_engine,
        patch("app.main.init_broker", AsyncMock(return_value=AsyncMock(spec=Broker))),
        patch("app.main.AIEngineClient"),
        patch("app.main.StorageService"),
    ):
        mock_engine.return_value = AsyncMock()

        from app.main import _startup

        await _startup(test_app)

    assert hasattr(test_app.state, "redis")
    assert hasattr(test_app.state, "engine")
    assert hasattr(test_app.state, "session_factory")
    assert hasattr(test_app.state, "ai_client")
    assert hasattr(test_app.state, "ws_manager")
    assert hasattr(test_app.state, "broker")
    assert hasattr(test_app.state, "storage")


@pytest.mark.asyncio
async def test_startup_broker_failure():
    test_app = FastAPI()

    with (
        patch("app.main.setup_logging"),
        patch("app.main.from_url", AsyncMock(return_value=AsyncMock())),
        patch("app.main.create_async_engine") as mock_engine,
        patch("app.main.init_broker", AsyncMock(side_effect=Exception("Broker down"))),
        patch("app.main.AIEngineClient"),
        patch("app.main.StorageService"),
    ):
        mock_engine.return_value = AsyncMock()

        from app.main import _startup

        await _startup(test_app)

    assert test_app.state.broker is None


@pytest.mark.asyncio
async def test_startup_storage_failure():
    test_app = FastAPI()

    with (
        patch("app.main.setup_logging"),
        patch("app.main.from_url", AsyncMock(return_value=AsyncMock())),
        patch("app.main.create_async_engine") as mock_engine,
        patch("app.main.init_broker", AsyncMock(return_value=AsyncMock(spec=Broker))),
        patch("app.main.AIEngineClient"),
        patch("app.main.StorageService") as mock_storage_cls,
    ):
        mock_instance = MagicMock()
        mock_instance.ensure_bucket = AsyncMock(side_effect=Exception("Storage down"))
        mock_storage_cls.return_value = mock_instance
        mock_engine.return_value = AsyncMock()

        from app.main import _startup

        await _startup(test_app)

    assert test_app.state.storage is None
