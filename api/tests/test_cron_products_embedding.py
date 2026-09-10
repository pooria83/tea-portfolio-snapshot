from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_admin_user
from app.main import app
from app.models.user import User
from app.services.embedding_config import DEFAULT_EMBEDDING_MODEL

MODEL_A = DEFAULT_EMBEDDING_MODEL
MODEL_B = "other/test-model"


async def _setup_admin(db_session: AsyncSession) -> str:
    user_id = str(uuid.uuid4())
    db_session.add(User(id=user_id, email=f"cron-admin-{uuid.uuid4().hex[:8]}@test.ai", role="admin"))
    await db_session.flush()
    return user_id


def _admin_headers(user_id: str) -> dict[str, str]:
    async def override() -> User:
        return User(id=user_id, email="cron-admin@test.ai", role="admin")

    app.dependency_overrides[get_admin_user] = override
    return {}


def _cleanup_override() -> None:
    app.dependency_overrides.pop(get_admin_user, None)


@pytest_asyncio.fixture
async def seed_cron_products(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=1)
    await db_session.execute(
        sa.text("""
            DELETE FROM product_embeddings
            WHERE product_id IN ('cp-done', 'cp-missing', 'cp-other')
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO users (id, email, role, hashed_password, phone, is_active, preferred_language)
            VALUES ('cron-test-user', 'cron@test.com', 'seller', 'dummy', '+96650000002', true, 'ar')
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO product_types (id, code, name_ar, name_en, name_fa, sort_order)
            VALUES ('pt-cron-test', 'cron-test', 'اختبار', 'Test', 'تست', 0)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO categories (id, product_type_id, name_ar, name_en, name_fa, sort_order, is_active)
            VALUES ('cat-cron-test', 'pt-cron-test', 'اختبار', 'Test', 'تست', 0, true)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO store_types (id, name_ar, name_en, name_fa, is_active)
            VALUES ('st-cron-test', 'اختبار', 'Test', 'تست', true)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO stores (id, owner_id, name, category_id, store_type_id, phone, address, location_lat, location_lng, country_code, price_unit_code, is_active)
            VALUES ('store-cron-test', 'cron-test-user', 'Cron Store', 'cat-cron-test', 'st-cron-test', '+96650000000', 'Addr', 24.71, 46.67, 'SA', 'SAR', true)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    for pid in ("cp-done", "cp-missing", "cp-other"):
        await db_session.execute(
            sa.text("""
                INSERT INTO store_products (id, store_id, product_type_id, category_id, status, has_variants, is_multi_piece, quantity, low_stock_threshold, currency, weight_unit, name_en, updated_at, created_at)
                VALUES (:id, 'store-cron-test', 'pt-cron-test', 'cat-cron-test', 'active', false, false, 0, 5, 'SAR', 'kg', :name, :now, :now)
                ON CONFLICT (id) DO NOTHING
            """),  # noqa: E501
            {"id": pid, "name": pid, "now": now},
        )
    await db_session.execute(
        sa.text("""
            INSERT INTO product_embeddings (id, product_id, model_name, embedding_status, embedding_error, updated_at)
            VALUES (md5('cp-done' || ':' || :model), 'cp-done', :model, 'done', NULL, :old)
            ON CONFLICT (id) DO UPDATE SET
                embedding_status = 'done',
                embedding_error = NULL,
                updated_at = :old
        """),
        {"model": MODEL_A, "old": old},
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO product_embeddings (id, product_id, model_name, embedding_status, updated_at)
            VALUES (md5('cp-other' || ':' || :model), 'cp-other', :model, 'error', :old)
            ON CONFLICT (id) DO UPDATE SET
                embedding_status = 'error',
                updated_at = :old
        """),
        {"model": MODEL_B, "old": old},
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_active_model_endpoint_returns_default(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user_id = await _setup_admin(db_session)
    try:
        resp = await client.get(
            "/api/v1/admin/cron/embedding-products/active-model",
            headers=_admin_headers(user_id),
        )
    finally:
        _cleanup_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["active_model"] == DEFAULT_EMBEDDING_MODEL


@pytest.mark.asyncio
async def test_active_model_requires_admin(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/cron/embedding-products/active-model")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reindex_marks_all_products_pending(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_cron_products: None,
) -> None:
    user_id = await _setup_admin(db_session)
    try:
        resp = await client.post(
            "/api/v1/admin/cron/embedding-products/reindex",
            headers=_admin_headers(user_id),
        )
    finally:
        _cleanup_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["active_model"] == DEFAULT_EMBEDDING_MODEL
    assert body["data"]["affected"] == 3

    result = await db_session.execute(
        sa.text("""
            SELECT embedding_status FROM product_embeddings
            WHERE model_name = :model ORDER BY product_id
        """),
        {"model": DEFAULT_EMBEDDING_MODEL},
    )
    statuses = [row[0] for row in result.all()]
    assert statuses == ["pending", "pending", "pending"]


@pytest.mark.asyncio
async def test_list_embedding_products_filters_by_model(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_cron_products: None,
) -> None:
    user_id = await _setup_admin(db_session)
    try:
        resp = await client.get(
            "/api/v1/admin/cron/embedding-products",
            params={"model": DEFAULT_EMBEDDING_MODEL},
            headers=_admin_headers(user_id),
        )
        resp_other = await client.get(
            "/api/v1/admin/cron/embedding-products",
            params={"model": MODEL_B},
            headers=_admin_headers(user_id),
        )
    finally:
        _cleanup_override()
    assert resp.status_code == 200
    body = resp.json()
    items = body["data"]
    assert body["meta"]["total"] == 1
    assert len(items) == 1
    assert items[0]["id"] == "cp-done"
    assert items[0]["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert items[0]["embedding_status"] == "done"

    assert resp_other.status_code == 200
    other_items = resp_other.json()["data"]
    assert len(other_items) == 1
    assert other_items[0]["id"] == "cp-other"
    assert other_items[0]["embedding_status"] == "error"


@pytest.mark.asyncio
async def test_list_embedding_products_filters_by_status(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_cron_products: None,
) -> None:
    user_id = await _setup_admin(db_session)
    try:
        resp = await client.get(
            "/api/v1/admin/cron/embedding-products",
            params={"embedding_status": "done"},
            headers=_admin_headers(user_id),
        )
    finally:
        _cleanup_override()
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert [i["id"] for i in items] == ["cp-done"]


@pytest.mark.asyncio
async def test_embedding_product_detail_returns_embeddings(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_cron_products: None,
) -> None:
    user_id = await _setup_admin(db_session)
    try:
        resp = await client.get(
            "/api/v1/admin/cron/embedding-products/cp-done",
            headers=_admin_headers(user_id),
        )
        resp_missing = await client.get(
            "/api/v1/admin/cron/embedding-products/does-not-exist",
            headers=_admin_headers(user_id),
        )
    finally:
        _cleanup_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    detail = body["data"]
    assert detail["id"] == "cp-done"
    assert len(detail["embeddings"]) == 1
    row = detail["embeddings"][0]
    assert row["model_name"] == DEFAULT_EMBEDDING_MODEL
    assert row["embedding_status"] == "done"
    assert row["embedding_error"] is None

    assert resp_missing.status_code == 404


@pytest.mark.asyncio
async def test_cron_summary_has_no_embedding_block(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user_id = await _setup_admin(db_session)
    try:
        resp = await client.get(
            "/api/v1/admin/cron/summary",
            headers=_admin_headers(user_id),
        )
    finally:
        _cleanup_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "llm" in body["data"]
    assert "embedding" not in body["data"]
