from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.crypto import encrypt_api_key
from app.core.deps import get_admin_user
from app.main import app
from app.models.llm import LLMApiKey, LLMModel
from app.models.user import User


async def _setup(user_id: str, db_session):
    user = User(
        id=user_id,
        email=f"admin-{uuid.uuid4().hex[:8]}@test.ai",
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()


def _override_admin_user(user_id: str):
    async def override():
        return User(id=user_id, email="admin@test.ai", role="admin")

    return override


async def _seed_models(db_session, prefix: str = ""):
    m1 = LLMModel(id=f"{prefix}model-1", provider="opencode_zen", model="deepseek-v4-flash-free")
    m2 = LLMModel(id=f"{prefix}model-2", provider="openrouter", model="gpt-oss-20b")
    db_session.add(m1)
    db_session.add(m2)


class TestListModels:
    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/llm/models")
        assert resp.status_code == 401

    async def test_forbidden(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/admin/llm/models", headers=auth_headers)
        assert resp.status_code == 403

    async def test_empty(self, client: AsyncClient, db_session):
        prefix = uuid.uuid4().hex[:8]
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await _seed_models(db_session, prefix)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.get("/api/v1/admin/llm/models")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert len(body["data"]) == 2
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_with_api_keys(self, client: AsyncClient, db_session):
        prefix = uuid.uuid4().hex[:8]
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await _seed_models(db_session, prefix)
        encrypted = encrypt_api_key("sk-test-key-12345")
        db_session.add(LLMApiKey(model_id=f"{prefix}model-1", api_key_encrypted=encrypted))
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.get("/api/v1/admin/llm/models")
            assert resp.status_code == 200
            data = resp.json()["data"]
            model1 = [m for m in data if m["id"] == f"{prefix}model-1"][0]
            assert len(model1["api_keys"]) == 1
            assert "****" in model1["api_keys"][0]["masked_key"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestAddApiKey:
    async def test_add_key(self, client: AsyncClient, db_session):
        prefix = uuid.uuid4().hex[:8]
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await _seed_models(db_session, prefix)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.post(
                "/api/v1/admin/llm/api-keys",
                json={
                    "model_id": f"{prefix}model-1",
                    "name": "Production",
                    "api_key": "sk-live-abcdef123456",
                },
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["success"] is True
            assert "****" in body["data"]["masked_key"]
            assert body["data"]["is_active"] is True
            assert body["data"]["model_id"] == f"{prefix}model-1"
            assert body["data"]["name"] == "Production"
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_add_key_without_name(self, client: AsyncClient, db_session):
        prefix = uuid.uuid4().hex[:8]
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await _seed_models(db_session, prefix)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.post(
                "/api/v1/admin/llm/api-keys",
                json={
                    "model_id": f"{prefix}model-1",
                    "api_key": "sk-no-name",
                },
            )
            assert resp.status_code == 201
            assert resp.json()["data"]["name"] is None
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_add_key_nonexistent_model(self, client: AsyncClient, db_session):
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.post(
                "/api/v1/admin/llm/api-keys",
                json={"model_id": "no-such-model", "api_key": "sk-test"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_add_key_encrypted(self, client: AsyncClient, db_session):
        prefix = uuid.uuid4().hex[:8]
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await _seed_models(db_session, prefix)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            await client.post(
                "/api/v1/admin/llm/api-keys",
                json={
                    "model_id": f"{prefix}model-1",
                    "api_key": "sk-raw-secret-value",
                },
            )
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

        result = await db_session.execute(select(LLMApiKey).where(LLMApiKey.model_id == f"{prefix}model-1"))
        key = result.scalar_one()
        assert key.api_key_encrypted != "sk-raw-secret-value"
        assert "sk-raw" not in key.api_key_encrypted

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/admin/llm/api-keys",
            json={"model_id": "model-1", "api_key": "sk-test"},
        )
        assert resp.status_code == 401


class TestToggleApiKey:
    async def test_toggle(self, client: AsyncClient, db_session):
        prefix = uuid.uuid4().hex[:8]
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await _seed_models(db_session, prefix)
        encrypted = encrypt_api_key("sk-test")
        key = LLMApiKey(model_id=f"{prefix}model-1", api_key_encrypted=encrypted)
        db_session.add(key)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.patch(
                f"/api/v1/admin/llm/api-keys/{key.id}/toggle",
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["is_active"] is False

            resp = await client.patch(
                f"/api/v1/admin/llm/api-keys/{key.id}/toggle",
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["is_active"] is True
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_toggle_not_found(self, client: AsyncClient, db_session):
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.patch(
                "/api/v1/admin/llm/api-keys/no-such-key/toggle",
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestDeleteApiKey:
    async def test_delete(self, client: AsyncClient, db_session):
        prefix = uuid.uuid4().hex[:8]
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await _seed_models(db_session, prefix)
        encrypted = encrypt_api_key("sk-test")
        key = LLMApiKey(model_id=f"{prefix}model-1", api_key_encrypted=encrypted)
        db_session.add(key)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.delete(
                f"/api/v1/admin/llm/api-keys/{key.id}",
            )
            assert resp.status_code == 204
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

        result = await db_session.execute(select(LLMApiKey).where(LLMApiKey.id == key.id))
        assert result.scalar_one_or_none() is None

    async def test_delete_not_found(self, client: AsyncClient, db_session):
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        await db_session.commit()

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.delete(
                "/api/v1/admin/llm/api-keys/no-such-key",
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_admin_user, None)
