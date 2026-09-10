import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import create_access_token
from app.core.password import hash_password
from app.models.category import Category
from app.models.product_type import ProductType
from app.models.store import Store
from app.models.store_product import StoreProduct
from app.models.store_type import StoreType
from app.models.user import User


async def _seed_store_with_products(db: AsyncSession, user_id: str) -> Store:
    st = StoreType(id=str(uuid.uuid4()), name_en="Retail", name_ar="Retail", name_fa="Retail", is_active=True)
    db.add(st)
    await db.flush()

    pt = ProductType(id="pt-stats", code="stats", name_en="Stats", name_ar="Stats", name_fa="Stats", sort_order=0)
    db.add(pt)
    await db.flush()

    cat = Category(id="cat-stats", product_type_id=pt.id, name_en="Stats", name_ar="Stats", name_fa="Stats", sort_order=0, is_active=True)
    db.add(cat)
    await db.flush()

    store = Store(
        id=str(uuid.uuid4()),
        owner_id=user_id,
        name="Stats Store",
        category_id=cat.id,
        store_type_id=st.id,
        phone="+966500000001",
        address="Test Address",
        location_lat=24.7136,
        location_lng=46.6753,
        country_code="KW",
        price_unit_code="KWD",
        is_active=True,
    )
    db.add(store)
    await db.flush()

    for status in ("active", "active", "draft"):
        db.add(
            StoreProduct(
                id=str(uuid.uuid4()),
                store_id=store.id,
                product_type_id=pt.id,
                status=status,
                name_en="Stats Product",
            )
        )
    await db.flush()

    return store


class TestMyProductsStats:
    @pytest.mark.asyncio
    async def test_counts_total_and_active(self, client: AsyncClient, db_session: AsyncSession, test_user: User, auth_headers):
        await _seed_store_with_products(db_session, test_user.id)

        resp = await client.get("/api/v1/stores/my/products/stats", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] == 3
        assert data["active"] == 2

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/stores/my/products/stats")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_user_without_stores_returns_zeroes(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="nostore@example.com",
            username="nostore",
            hashed_password=hash_password("TestPass123!"),
            full_name="No Store",
            role="user",
        )
        db_session.add(user)
        await db_session.flush()
        token = create_access_token(user.id, user.role)

        resp = await client.get("/api/v1/stores/my/products/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data == {"total": 0, "active": 0}
