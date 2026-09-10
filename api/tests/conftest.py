import os
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.ai.client import AIEngineClient
from app.core.broker import Broker
from app.core.config import settings

settings.api_key = "test-api-key"
settings.secret_key = "test-secret-key"
settings.jwt_secret_key = "test-jwt-secret-which-is-long-enough-now!"
settings.debug = True
settings.google_web_client_id = ""
settings.google_android_client_id = ""

from cryptography.fernet import Fernet  # noqa: E402

from app.core import crypto as _crypto  # noqa: E402

settings.llm_encryption_key = Fernet.generate_key().decode()
_crypto._cipher = None

from app.core.database import get_db  # noqa: E402
from app.core.jwt import create_access_token  # noqa: E402
from app.core.password import hash_password  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.ws_manager import ConnectionManager  # noqa: E402


def _mock_broker() -> AsyncMock:
    mock = AsyncMock(spec=Broker)
    mock.channel = AsyncMock()
    mock.channel.default_exchange = AsyncMock()
    mock.is_connected = lambda: True
    return mock


def _mock_ai_client() -> AsyncMock:
    mock = AsyncMock(spec=AIEngineClient)
    mock.health.return_value = True
    return mock


@pytest.fixture(scope="session")
def postgres_container():
    if os.getenv("TEST_DATABASE_URL"):
        yield None
        return
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    yield container
    container.stop()


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_container):
    db_url = os.getenv("TEST_DATABASE_URL")
    if db_url is None:
        host = postgres_container.get_container_host_ip()
        port = postgres_container.get_exposed_port(5432)
        db_url = f"postgresql+asyncpg://{postgres_container.username}:{postgres_container.password}@{host}:{port}/{postgres_container.dbname}"

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True, connect_args={"ssl": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            sa.text("""INSERT INTO countries (code, name_ar, name_en, name_fa) VALUES
            ('SA', 'المملكة العربية السعودية', 'Saudi Arabia', 'عربستان سعودی'),
            ('KW', 'الكويت', 'Kuwait', 'کویت'),
            ('AE', 'الإمارات العربية المتحدة', 'United Arab Emirates', 'امارات متحده عربی')
            ON CONFLICT DO NOTHING""")
        )
        await conn.execute(
            sa.text("""INSERT INTO currencies (code, name_ar, name_en, name_fa, symbol) VALUES
            ('SAR', 'ريال سعودي', 'Saudi Riyal', 'ریال سعودی', '﷼'),
            ('KWD', 'دينار كويتي', 'Kuwaiti Dinar', 'دینار کویت', 'د.ك'),
            ('AED', 'درهم إماراتي', 'UAE Dirham', 'درهم امارات', 'د.إ')
            ON CONFLICT DO NOTHING""")
        )

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    app.state.engine = engine
    app.state.session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with app.state.session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mongo_client: AsyncMongoMockClient) -> AsyncGenerator[AsyncClient, None]:
    _redis_store: dict[str, str] = {}

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.eval = AsyncMock(side_effect=NotImplementedError("no script support in unit tests"))

    def _incr(key: str) -> int:
        val = int(_redis_store.get(key, "0")) + 1
        _redis_store[key] = str(val)
        return val

    async def _set(key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in _redis_store:
            return False
        _redis_store[key] = value
        return True

    async def _delete(*keys: str) -> int:
        return sum(1 for k in keys if _redis_store.pop(k, None) is not None)

    async def _scan_iter(match: str = "*", count: int = 100):  # noqa: ARG002
        prefix = match.rstrip("*") if match.endswith("*") else match
        for key in list(_redis_store):
            if key.startswith(prefix):
                yield key

    mock_redis.incr = AsyncMock(side_effect=_incr)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(side_effect=lambda key: _redis_store.get(key))
    mock_redis.setex = AsyncMock(side_effect=lambda key, ttl, value: _redis_store.update({key: value}) or True)
    mock_redis.setex_bytes = AsyncMock(side_effect=lambda key, ttl, value: _redis_store.update({key: value}) or True)
    mock_redis.delete = AsyncMock(side_effect=_delete)
    mock_redis.exists = AsyncMock(side_effect=lambda key: 1 if key in _redis_store else 0)
    mock_redis.set = AsyncMock(side_effect=_set)
    mock_redis.getdel = AsyncMock(side_effect=lambda key: _redis_store.pop(key, None))
    mock_redis.scan_iter = _scan_iter

    async def override_get_db():
        yield db_session

    def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    app.state.redis = mock_redis
    app.state.ai_client = _mock_ai_client()
    app.state.broker = _mock_broker()
    app.state.ws_manager = ConnectionManager()
    app.state.mongo_db = SimpleNamespace(db=mongo_client[settings.mongo_db_name])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    for attr in ("redis", "ai_client", "broker", "ws_manager", "storage", "temp_storage", "profile_storage", "store_storage", "mongo_db"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


@pytest_asyncio.fixture(scope="session")
async def mongo_client() -> AsyncGenerator[AsyncMongoMockClient, None]:
    client = AsyncMongoMockClient()
    yield client


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        role="user",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        username="adminuser",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin User",
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id, test_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(admin_user.id, admin_user.role)
    return {"Authorization": f"Bearer {token}"}
