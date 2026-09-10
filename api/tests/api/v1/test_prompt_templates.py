from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.deps import get_admin_user
from app.main import app
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.services import prompt_defaults

PATH = "/api/v1/admin/llm/prompt-templates"


async def _setup_admin(user_id: str, db_session) -> None:
    db_session.add(User(id=user_id, email=f"admin-{uuid.uuid4().hex[:8]}@test.ai", role="admin"))
    await db_session.flush()


def _override_admin(user_id: str):
    async def override():
        return User(id=user_id, email="admin@test.ai", role="admin")

    return override


async def _reset_prompts(db_session) -> None:
    await db_session.execute(delete(PromptTemplate))
    await db_session.flush()


def _defaults() -> dict[str, str]:
    return {
        "pre_prompt": prompt_defaults.DEFAULT_PRE_PROMPT,
        "ending_prompt": prompt_defaults.DEFAULT_ENDING_PROMPT,
        "chat_assistant": prompt_defaults.DEFAULT_CHAT_ASSISTANT_PROMPT,
        "parse_query": prompt_defaults.DEFAULT_PARSE_QUERY_PROMPT,
        "summarize": prompt_defaults.DEFAULT_SUMMARIZE_PROMPT,
        "title": prompt_defaults.DEFAULT_TITLE_PROMPT,
    }


class TestGetPromptTemplates:
    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get(PATH)
        assert resp.status_code == 401

    async def test_forbidden(self, client: AsyncClient, auth_headers):
        resp = await client.get(PATH, headers=auth_headers)
        assert resp.status_code == 403

    async def test_defaults_when_nothing_seeded(self, client: AsyncClient, db_session):
        await _reset_prompts(db_session)
        user_id = str(uuid.uuid4())
        await _setup_admin(user_id, db_session)
        await db_session.commit()
        app.dependency_overrides[get_admin_user] = _override_admin(user_id)
        try:
            resp = await client.get(PATH)
            assert resp.status_code == 200
            data = resp.json()["data"]
            for key, default in _defaults().items():
                assert data[key] == default
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_active_row_wins(self, client: AsyncClient, db_session):
        await _reset_prompts(db_session)
        user_id = str(uuid.uuid4())
        await _setup_admin(user_id, db_session)
        db_session.add(PromptTemplate(id=str(uuid.uuid4()), type="title", content="custom title prompt", is_active=True))
        await db_session.commit()
        app.dependency_overrides[get_admin_user] = _override_admin(user_id)
        try:
            resp = await client.get(PATH)
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["title"] == "custom title prompt"
            assert data["chat_assistant"] == prompt_defaults.DEFAULT_CHAT_ASSISTANT_PROMPT
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUpdatePromptTemplates:
    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.put(PATH, json={"title": "x"})
        assert resp.status_code == 401

    async def test_partial_update(self, client: AsyncClient, db_session):
        await _reset_prompts(db_session)
        user_id = str(uuid.uuid4())
        await _setup_admin(user_id, db_session)
        await db_session.commit()
        app.dependency_overrides[get_admin_user] = _override_admin(user_id)
        try:
            resp = await client.put(PATH, json={"title": "Titles for shoppers"})
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["title"] == "Titles for shoppers"
            assert data["pre_prompt"] == prompt_defaults.DEFAULT_PRE_PROMPT

            rows = (await db_session.execute(select(PromptTemplate).where(PromptTemplate.type == "title"))).scalars().all()
            assert len(rows) == 1
            assert rows[0].is_active is True
            assert rows[0].content == "Titles for shoppers"
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_update_all_types_deactivates_old(self, client: AsyncClient, db_session):
        await _reset_prompts(db_session)
        user_id = str(uuid.uuid4())
        await _setup_admin(user_id, db_session)
        await db_session.commit()
        app.dependency_overrides[get_admin_user] = _override_admin(user_id)
        try:
            body = {key: f"{key}-v1" for key in _defaults()}
            resp = await client.put(PATH, json=body)
            assert resp.status_code == 200
            assert resp.json()["data"] == body

            resp = await client.put(PATH, json={"chat_assistant": "chat-assistant-v2"})
            assert resp.status_code == 200
            assert resp.json()["data"]["chat_assistant"] == "chat-assistant-v2"

            rows = (await db_session.execute(select(PromptTemplate).where(PromptTemplate.type == "chat_assistant"))).scalars().all()
            assert len(rows) == 2
            assert sum(1 for r in rows if r.is_active) == 1
            assert next(r for r in rows if r.is_active).content == "chat-assistant-v2"
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    async def test_empty_body_changes_nothing(self, client: AsyncClient, db_session):
        await _reset_prompts(db_session)
        user_id = str(uuid.uuid4())
        await _setup_admin(user_id, db_session)
        await db_session.commit()
        app.dependency_overrides[get_admin_user] = _override_admin(user_id)
        try:
            resp = await client.put(PATH, json={})
            assert resp.status_code == 200
            for key, default in _defaults().items():
                assert resp.json()["data"][key] == default
        finally:
            app.dependency_overrides.pop(get_admin_user, None)
