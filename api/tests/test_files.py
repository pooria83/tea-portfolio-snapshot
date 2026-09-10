from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.redis import get_redis
from app.main import app
from app.services.storage_service import StorageService
from app.services.ws_manager import ConnectionManager


@pytest.fixture
def mock_storage(test_user):
    mock = AsyncMock(spec=StorageService)
    mock.upload_file.return_value = "uuid-file.csv"
    mock.get_public_url.side_effect = lambda name: f"http://presigned/minio/{name}"
    mock.stat_file.return_value = {
        "size": 100,
        "content_type": "text/plain",
        "metadata": {"original_name": "original.txt", "uploaded_by": test_user.id},
        "last_modified": "2025-01-01T00:00:00+00:00",
    }
    mock.delete_file.return_value = None
    return mock


def _setup_app(mock_storage, db_session):
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=True)

    async def override_get_db():
        yield db_session

    def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.state.redis = mock_redis
    app.state.ai_client = AsyncMock()
    app.state.broker = AsyncMock()
    app.state.ws_manager = ConnectionManager()
    app.state.storage = mock_storage
    app.state.temp_storage = mock_storage

    return app


def _teardown_app():
    app.dependency_overrides.clear()
    for attr in ("storage", "temp_storage", "redis", "ai_client", "broker", "ws_manager"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


@pytest.mark.asyncio
async def test_upload_file_requires_auth(db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/files/upload")
    assert resp.status_code == 401
    _teardown_app()


@pytest.mark.asyncio
async def test_upload_file_success(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/files/upload",
            files={"file": ("test.csv", b"a,b,c\n1,2,3", "text/csv")},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_name"] == "uuid-file.csv"
    assert data["original_name"] == "test.csv"
    assert data["content_type"] == "text/csv"
    assert data["size"] == 11
    assert data["url"] == "http://presigned/minio/uuid-file.csv"
    _teardown_app()


@pytest.mark.asyncio
async def test_get_file_requires_auth(db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/files/my-file.txt")
    assert resp.status_code == 401
    _teardown_app()


@pytest.mark.asyncio
async def test_get_file_success(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/files/my-file.txt", headers=auth_headers, follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "http://presigned/minio/my-file.txt"
    _teardown_app()


@pytest.mark.asyncio
async def test_get_file_not_found(auth_headers, db_session, mock_storage):
    mock_storage.stat_file.return_value = None
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/files/missing.txt", headers=auth_headers)
    assert resp.status_code == 404
    _teardown_app()


@pytest.mark.asyncio
async def test_delete_file_success(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/files/to-delete.txt", headers=auth_headers)
    assert resp.status_code == 204
    mock_storage.delete_file.assert_called_once_with("to-delete.txt")
    _teardown_app()


@pytest.mark.asyncio
async def test_delete_file_requires_auth(db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/files/to-delete.txt")
    assert resp.status_code == 401
    _teardown_app()


@pytest.mark.asyncio
async def test_upload_file_disallowed_extension(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/files/upload",
            files={"file": ("malware.exe", b"fake", "application/x-msdownload")},
            headers=auth_headers,
        )
    assert resp.status_code == 422
    _teardown_app()


@pytest.mark.asyncio
async def test_upload_file_magic_bytes_mismatch(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/files/upload",
            files={"file": ("image.jpg", b"not-an-image", "image/jpeg")},
            headers=auth_headers,
        )
    assert resp.status_code == 422
    _teardown_app()


@pytest.mark.asyncio
async def test_get_file_path_traversal_rejected(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/files/..%2F..%2Fetc%2Fpasswd", headers=auth_headers)
    assert resp.status_code == 422
    _teardown_app()


@pytest.mark.asyncio
async def test_upload_file_too_large(auth_headers, db_session, mock_storage, monkeypatch):
    monkeypatch.setattr("app.api.v1.files.settings.max_upload_size", 10)
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/files/upload",
            files={"file": ("big.txt", b"x" * 20, "text/plain")},
            headers=auth_headers,
        )
    assert resp.status_code == 422
    _teardown_app()


@pytest.mark.asyncio
async def test_upload_file_bad_content_type(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/files/upload",
            files={"file": ("test.xyz", b"some data", "application/x-xyz")},
            headers=auth_headers,
        )
    assert resp.status_code == 422
    _teardown_app()


@pytest.mark.asyncio
async def test_upload_file_webp_valid(auth_headers, db_session, mock_storage):
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/files/upload",
            files={"file": ("image.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp")},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    _teardown_app()


@pytest.mark.asyncio
async def test_get_file_idor_rejected(auth_headers, db_session, mock_storage):
    mock_storage.stat_file.return_value = {
        "size": 100,
        "content_type": "text/plain",
        "metadata": {"uploaded_by": "other-user"},
        "last_modified": "2025-01-01T00:00:00+00:00",
    }
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/files/others-file.txt", headers=auth_headers, follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "http://presigned/minio/others-file.txt"
    _teardown_app()


@pytest.mark.asyncio
async def test_delete_file_not_found(auth_headers, db_session, mock_storage):
    mock_storage.stat_file.return_value = None
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/files/missing.txt", headers=auth_headers)
    assert resp.status_code == 404
    _teardown_app()


@pytest.mark.asyncio
async def test_delete_file_idor_rejected(auth_headers, db_session, mock_storage):
    mock_storage.stat_file.return_value = {
        "size": 100,
        "content_type": "text/plain",
        "metadata": {"uploaded_by": "other-user"},
        "last_modified": "2025-01-01T00:00:00+00:00",
    }
    _setup_app(mock_storage, db_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/files/others-file.txt", headers=auth_headers)
    assert resp.status_code == 404
    _teardown_app()
