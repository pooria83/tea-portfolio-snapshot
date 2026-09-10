import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.jwt import create_access_token
from app.models.brand import Brand
from app.models.category import Category
from app.models.product_image import ProductImage
from app.models.product_type import ProductType
from app.models.store import Store
from app.models.store_product import StoreProduct
from app.models.store_type import StoreType
from app.models.user import User
from app.models.user_favorite import UserFavorite


async def _seed_store_product(db: AsyncSession, user: User, *, name_en: str = "Nike Air", brand: bool = True) -> tuple[Store, StoreProduct]:
    db.add(
        ProductType(
            id="pt-fav",
            code="favorites-test",
            name_en="Clothing",
            name_ar="ملابس",
            name_fa="پوشاک",
        )
    )
    db.add(
        Category(
            id="cat-fav",
            name_en="Shirts",
            name_ar="قمصان",
            name_fa="پیراهن",
        )
    )
    db.add(
        StoreType(
            id="st-fav",
            name_en="Fashion",
            name_ar="أزياء",
            name_fa="مد",
        )
    )
    await db.flush()

    if brand:
        db.add(Brand(id="brand-fav", code="nike-test", name_en="Nike", name_ar="نايك", name_fa="نایکی"))
        await db.flush()

    store = Store(
        id="store-fav",
        owner_id=user.id,
        name="Nike Store",
        category_id="cat-fav",
        store_type_id="st-fav",
        phone="+966500000000",
        address="Riyadh",
        location_lat=24.7,
        location_lng=46.7,
        country_code="SA",
        price_unit_code="SAR",
    )
    product = StoreProduct(
        id="product-fav",
        store_id="store-fav",
        product_type_id="pt-fav",
        category_id="cat-fav",
        name_en=name_en,
        name_ar=name_en,
        name_fa=name_en,
        brand="brand-fav" if brand else None,
        status="active",
        price=199.0,
        original_price=249.0,
        sale_price=179.0,
        currency="SAR",
    )
    db.add_all([store, product])
    await db.flush()
    db.add(ProductImage(product_id=product.id, image_url="product-graph/test.jpg", sort_order=0))
    await db.flush()
    return store, product


async def _count_favorites(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(select(func.count()).select_from(UserFavorite).where(UserFavorite.user_id == user_id))
    return result.scalar_one()


class TestFavoritesApi:
    async def test_add_favorite_and_list(self, client: AsyncClient, test_user: User, db_session: AsyncSession, auth_headers: dict[str, str]) -> None:
        _, product = await _seed_store_product(db_session, test_user)

        resp = await client.put(f"/api/v1/users/me/favorites/{product.store_id}/{product.id}", headers=auth_headers)
        assert resp.status_code == 204

        resp = await client.get("/api/v1/users/me/favorites", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        item = data[0]
        assert item["id"] == product.id
        assert item["store_id"] == product.store_id
        assert item["store_name"] == "Nike Store"
        assert item["name_en"] == "Nike Air"
        assert item["brand"] == "Nike"
        assert item["price"] == 199.0
        assert item["currency"] == "SAR"
        assert item["image_url"] == f"{settings.minio_public_url}/product-graph/test.jpg"
        assert item["created_at"] is not None

    async def test_add_favorite_is_idempotent(self, client: AsyncClient, test_user: User, db_session: AsyncSession, auth_headers: dict[str, str]) -> None:
        _, product = await _seed_store_product(db_session, test_user)

        resp1 = await client.put(f"/api/v1/users/me/favorites/{product.store_id}/{product.id}", headers=auth_headers)
        resp2 = await client.put(f"/api/v1/users/me/favorites/{product.store_id}/{product.id}", headers=auth_headers)
        assert resp1.status_code == 204
        assert resp2.status_code == 204
        assert await _count_favorites(db_session, test_user.id) == 1

    async def test_remove_favorite(self, client: AsyncClient, test_user: User, db_session: AsyncSession, auth_headers: dict[str, str]) -> None:
        _, product = await _seed_store_product(db_session, test_user)
        await client.put(f"/api/v1/users/me/favorites/{product.store_id}/{product.id}", headers=auth_headers)

        resp = await client.delete(f"/api/v1/users/me/favorites/{product.store_id}/{product.id}", headers=auth_headers)
        assert resp.status_code == 204
        assert await _count_favorites(db_session, test_user.id) == 0

        resp = await client.get("/api/v1/users/me/favorites", headers=auth_headers)
        assert resp.json()["data"] == []

    async def test_remove_missing_favorite_is_noop(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        resp = await client.delete(f"/api/v1/users/me/favorites/{uuid.uuid4()}/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_add_favorite_unknown_product_returns_404(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        resp = await client.put(f"/api/v1/users/me/favorites/{uuid.uuid4()}/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["translation_key"] == "product_not_found"

    async def test_favorites_require_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/users/me/favorites")
        assert resp.status_code == 401
        resp = await client.put(f"/api/v1/users/me/favorites/{uuid.uuid4()}/{uuid.uuid4()}")
        assert resp.status_code == 401
        resp = await client.delete(f"/api/v1/users/me/favorites/{uuid.uuid4()}/{uuid.uuid4()}")
        assert resp.status_code == 401

    async def test_favorites_are_scoped_per_user(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
        auth_headers: dict[str, str],
    ) -> None:
        _, product = await _seed_store_product(db_session, test_user)

        other = User(email="other@example.com", username="otheruser", role="user")
        db_session.add(other)
        await db_session.flush()

        other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.role)}"}

        await client.put(f"/api/v1/users/me/favorites/{product.store_id}/{product.id}", headers=auth_headers)

        resp = await client.get("/api/v1/users/me/favorites", headers=other_headers)
        assert resp.json()["data"] == []

    async def test_pagination(self, client: AsyncClient, test_user: User, db_session: AsyncSession, auth_headers: dict[str, str]) -> None:
        _, product = await _seed_store_product(db_session, test_user)
        product2 = StoreProduct(
            id="product-fav-2",
            store_id=product.store_id,
            product_type_id="pt-fav",
            name_en="Second",
            name_ar="Second",
            name_fa="Second",
            status="active",
            price=99.0,
            currency="SAR",
        )
        db_session.add(product2)
        await db_session.flush()
        for pid in (product.id, product2.id):
            await client.put(f"/api/v1/users/me/favorites/{product.store_id}/{pid}", headers=auth_headers)

        resp = await client.get("/api/v1/users/me/favorites?skip=0&limit=1", headers=auth_headers)
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["meta"]["total"] == 2
        assert data["meta"]["has_next"] is True
        first_id = data["data"][0]["id"]

        resp = await client.get("/api/v1/users/me/favorites?skip=1&limit=1", headers=auth_headers)
        assert resp.json()["data"][0]["id"] != first_id

    async def test_no_favorites_returns_empty_list(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        resp = await client.get("/api/v1/users/me/favorites", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["meta"]["total"] == 0

    async def test_deleted_product_disappears_from_favorites(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
        auth_headers: dict[str, str],
    ) -> None:
        _, product = await _seed_store_product(db_session, test_user)
        await client.put(f"/api/v1/users/me/favorites/{product.store_id}/{product.id}", headers=auth_headers)

        await db_session.delete(await db_session.get(StoreProduct, product.id))
        await db_session.flush()

        resp = await client.get("/api/v1/users/me/favorites", headers=auth_headers)
        assert resp.json()["data"] == []
