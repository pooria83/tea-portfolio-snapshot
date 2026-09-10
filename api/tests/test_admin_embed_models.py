from __future__ import annotations

import json
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.crypto import decrypt_api_key, encrypt_api_key
from app.core.deps import get_admin_user
from app.main import app
from app.models.embed_model import EmbedModel
from app.models.system_setting import SystemSetting
from app.models.user import User


async def _setup(user_id: str, db_session) -> None:
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


def _embed_model_name(suffix: str) -> str:
    return f"Test-{uuid.uuid4().hex[:8]}-{suffix}"


async def _seed_embed_model(db_session, model_name: str) -> None:
    db_session.add(EmbedModel(id=f"embed-{uuid.uuid4().hex[:12]}", model_name=model_name, display_name=model_name))
    await db_session.commit()


class TestListEmbedModels:
    async def test_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/admin/embed-models")
        assert resp.status_code == 401

    async def test_forbidden(self, client: AsyncClient, auth_headers) -> None:
        resp = await client.get("/api/v1/admin/embed-models", headers=auth_headers)
        assert resp.status_code == 403

    async def test_list_models(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        m1 = _embed_model_name("M1")
        m2 = _embed_model_name("M2")
        await _seed_embed_model(db_session, m1)
        await _seed_embed_model(db_session, m2)

        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        try:
            resp = await client.get("/api/v1/admin/embed-models")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            names = {m["model_name"] for m in body["data"]}
            assert {m1, m2} <= names
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUpdateEmbeddingProvider:
    async def _put_provider(self, client: AsyncClient, value: str, user_id: str):
        app.dependency_overrides[get_admin_user] = _override_admin_user(user_id)
        resp = None
        try:
            resp = await client.put("/api/v1/admin/system-settings", json={"key": "embedding_provider", "value": value})
        finally:
            app.dependency_overrides.pop(get_admin_user, None)
        assert resp is not None
        return resp

    async def test_valid_tei_config_encrypts_api_key(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        model = _embed_model_name("BGE")
        await _seed_embed_model(db_session, model)

        value = json.dumps(
            {
                "provider": "tei",
                "model": model,
                "base_url": "https://tunnel.example.com/v1",
                "need_api_key": True,
                "api_key": "sk-abc12345",
            }
        )
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 200

        result = await db_session.execute(select(SystemSetting).where(SystemSetting.key == "embedding_provider"))
        stored = json.loads(result.scalar_one().value)
        assert stored["provider"] == "tei"
        assert stored["model"] == model
        assert stored["base_url"] == "https://tunnel.example.com/v1"
        assert stored["api_key_encrypted"] is True
        assert stored["api_key"] != "sk-abc12345"
        assert decrypt_api_key(stored["api_key"]) == "sk-abc12345"

    async def test_valid_tei_config_without_key(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        model = _embed_model_name("Qwen3")
        await _seed_embed_model(db_session, model)

        value = json.dumps(
            {
                "provider": "tei",
                "model": model,
                "base_url": "https://tunnel.example.com/v1",
                "need_api_key": False,
                "api_key": "",
            }
        )
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 200

        result = await db_session.execute(select(SystemSetting).where(SystemSetting.key == "embedding_provider"))
        stored = json.loads(result.scalar_one().value)
        assert stored["api_key"] == ""
        assert stored["api_key_encrypted"] is False

    async def test_missing_model_rejected(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)

        value = json.dumps({"provider": "tei", "base_url": "https://tunnel.example.com/v1"})
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 422
        assert resp.json()["error"]["translation_key"] == "embed_model_required"

    async def test_unknown_model_rejected(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)

        value = json.dumps({"provider": "tei", "model": "not-a-real-model", "base_url": "https://tunnel.example.com/v1"})
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 422
        assert resp.json()["error"]["translation_key"] == "embed_model_not_found"

    async def test_missing_tunnel_url_rejected(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        model = _embed_model_name("BGE")
        await _seed_embed_model(db_session, model)

        value = json.dumps({"provider": "tei", "model": model})
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 422
        assert resp.json()["error"]["translation_key"] == "embed_tunnel_url_required"

    async def test_missing_api_key_rejected(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        model = _embed_model_name("BGE")
        await _seed_embed_model(db_session, model)

        value = json.dumps({"provider": "tei", "model": model, "base_url": "https://tunnel.example.com/v1", "need_api_key": True})
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 422
        assert resp.json()["error"]["translation_key"] == "embed_api_key_required"

    async def test_short_api_key_rejected(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        model = _embed_model_name("BGE")
        await _seed_embed_model(db_session, model)

        value = json.dumps(
            {
                "provider": "tei",
                "model": model,
                "base_url": "https://tunnel.example.com/v1",
                "need_api_key": True,
                "api_key": "sk",
            }
        )
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 422
        assert resp.json()["error"]["translation_key"] == "embed_api_key_too_short"

    async def test_keeps_stored_key_when_empty(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)
        model = _embed_model_name("BGE")
        await _seed_embed_model(db_session, model)

        leftover = await db_session.execute(select(SystemSetting).where(SystemSetting.key == "embedding_provider"))
        for row in leftover.scalars():
            await db_session.delete(row)
        await db_session.commit()

        encrypted = encrypt_api_key("sk-keep-me-12345")
        db_session.add(
            SystemSetting(
                id=str(uuid.uuid4()),
                key="embedding_provider",
                value=json.dumps(
                    {
                        "provider": "tei",
                        "model": model,
                        "base_url": "https://tunnel.example.com/v1",
                        "need_api_key": True,
                        "api_key": encrypted,
                        "api_key_encrypted": True,
                    }
                ),
            )
        )
        await db_session.commit()

        value = json.dumps(
            {
                "provider": "tei",
                "model": model,
                "base_url": "https://tunnel.example.com/v1",
                "need_api_key": True,
                "api_key": "",
            }
        )
        resp = await self._put_provider(client, value, user_id)
        assert resp.status_code == 200

        result = await db_session.execute(select(SystemSetting).where(SystemSetting.key == "embedding_provider"))
        stored = json.loads(result.scalar_one().value)
        assert stored["api_key"] == encrypted
        assert stored["api_key_encrypted"] is True

    async def test_legacy_plain_provider_still_accepted(self, client: AsyncClient, db_session) -> None:
        user_id = str(uuid.uuid4())
        await _setup(user_id, db_session)

        resp = await self._put_provider(client, "sentence_transformer", user_id)
        assert resp.status_code == 200

        result = await db_session.execute(select(SystemSetting).where(SystemSetting.key == "embedding_provider"))
        assert json.loads(result.scalar_one().value) == {"provider": "sentence_transformer"}
