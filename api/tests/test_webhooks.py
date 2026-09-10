from __future__ import annotations

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

MODEL = "Qwen/Qwen3-Embedding-0.6B"


async def _seed_product(db_session: AsyncSession, product_id: str, name_en: str) -> None:
    await db_session.execute(
        sa.text("""
            INSERT INTO users (id, email, role, hashed_password, phone, is_active, preferred_language)
            VALUES ('wh-test-user', 'wh-test@test.com', 'seller', 'dummy', '+96650000001', true, 'ar')
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO product_types (id, code, name_ar, name_en, name_fa, sort_order)
            VALUES ('pt-wh-test', 'wh-test', 'اختبار', 'Test', 'تست', 0)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO categories (id, product_type_id, name_ar, name_en, name_fa, sort_order, is_active)
            VALUES ('cat-wh-test', 'pt-wh-test', 'اختبار', 'Test', 'تست', 0, true)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO store_types (id, name_ar, name_en, name_fa, is_active)
            VALUES ('st-wh-test', 'اختبار', 'Test', 'تست', true)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO stores (id, owner_id, name, category_id, store_type_id, phone, address, location_lat, location_lng, country_code, price_unit_code, is_active)
            VALUES ('store-wh-test', 'wh-test-user', 'Test Store', 'cat-wh-test', 'st-wh-test', '+96650000000', 'Addr', 24.71, 46.67, 'SA', 'SAR', true)
            ON CONFLICT (id) DO NOTHING
        """),
    )
    now = datetime.now(UTC)
    await db_session.execute(
        sa.text("""
            INSERT INTO store_products (id, store_id, product_type_id, category_id, status, has_variants, is_multi_piece, quantity, low_stock_threshold, currency, weight_unit, name_en, updated_at, created_at)
            VALUES (:id, 'store-wh-test', 'pt-wh-test', 'cat-wh-test', 'active', false, false, 0, 5, 'SAR', 'kg', :name_en, :now, :now)
            ON CONFLICT (id) DO NOTHING
        """),  # noqa: E501
        {"id": product_id, "name_en": name_en, "now": now},
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO product_embeddings (id, product_id, model_name, embedding_status)
            VALUES (md5(:product_id || ':' || :model), :product_id, :model, 'generating')
            ON CONFLICT (product_id, model_name) DO NOTHING
        """),
        {"product_id": product_id, "model": MODEL},
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_webhook_success_updates_done(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _seed_product(db_session, "sp-wh-done", "Webhook Test")

    resp = await client.post(
        "/api/v1/webhook/embedding-result",
        json={"product_id": "sp-wh-done", "lang": "en", "status": "done", "model": MODEL},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    result = await db_session.execute(
        sa.text("SELECT embedding_status, embedding_error FROM product_embeddings WHERE product_id = 'sp-wh-done' AND model_name = :model"),
        {"model": MODEL},
    )
    row = result.one_or_none()
    assert row is not None
    assert row[0] == "done"
    assert row[1] is None


@pytest.mark.asyncio
async def test_webhook_error_updates_error(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _seed_product(db_session, "sp-wh-error", "Webhook Error")

    resp = await client.post(
        "/api/v1/webhook/embedding-result",
        json={
            "product_id": "sp-wh-error",
            "lang": "en",
            "status": "error",
            "error": "Qdrant connection refused",
            "model": MODEL,
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    result = await db_session.execute(
        sa.text("SELECT embedding_status, embedding_error FROM product_embeddings WHERE product_id = 'sp-wh-error' AND model_name = :model"),
        {"model": MODEL},
    )
    row = result.one_or_none()
    assert row is not None
    assert row[0] == "error"
    assert row[1] == "Qdrant connection refused"


@pytest.mark.asyncio
async def test_webhook_without_model_uses_active_model(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _seed_product(db_session, "sp-wh-nomodel", "Webhook No Model")

    resp = await client.post(
        "/api/v1/webhook/embedding-result",
        json={"product_id": "sp-wh-nomodel", "lang": "en", "status": "done"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    result = await db_session.execute(
        sa.text("SELECT embedding_status FROM product_embeddings WHERE product_id = 'sp-wh-nomodel' AND model_name = :model"),
        {"model": MODEL},
    )
    row = result.one_or_none()
    assert row is not None
    assert row[0] == "done"


@pytest.mark.asyncio
async def test_webhook_rejects_missing_secret_when_configured(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    await _seed_product(db_session, "sp-wh-nosec", "Webhook No Secret")

    resp = await client.post(
        "/api/v1/webhook/embedding-result",
        json={"product_id": "sp-wh-nosec", "lang": "en", "status": "done", "model": MODEL},
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret_when_configured(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    await _seed_product(db_session, "sp-wh-wrong", "Webhook Wrong Secret")

    resp = await client.post(
        "/api/v1/webhook/embedding-result",
        json={"product_id": "sp-wh-wrong", "lang": "en", "status": "done", "model": MODEL},
        headers={"X-Webhook-Secret": "nope"},
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_secret_via_header(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    await _seed_product(db_session, "sp-wh-hdr", "Webhook Header Secret")

    resp = await client.post(
        "/api/v1/webhook/embedding-result",
        json={"product_id": "sp-wh-hdr", "lang": "en", "status": "done", "model": MODEL},
        headers={"X-Webhook-Secret": "s3cr3t"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_accepts_secret_via_query(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    await _seed_product(db_session, "sp-wh-qry", "Webhook Query Secret")

    resp = await client.post(
        "/api/v1/webhook/embedding-result?token=s3cr3t",
        json={"product_id": "sp-wh-qry", "lang": "en", "status": "done", "model": MODEL},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_bootstrap_webhook_requires_secret_when_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")

    resp = await client.post("/api/v1/webhook/ai-engine-bootstrap", json={})

    assert resp.status_code == 401
