from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.brand import Brand
from app.models.category import Category
from app.models.product_image import ProductImage
from app.models.product_type import ProductType
from app.models.store import Store
from app.models.store_product import StoreProduct
from app.models.store_type import StoreType
from app.models.user import User


async def _ensure_shared_rows(db: AsyncSession) -> None:
    result = await db.execute(select(ProductType).where(ProductType.id == "pt-public"))
    if not result.scalar_one_or_none():
        db.add(
            ProductType(
                id="pt-public",
                code="public-random-test",
                name_en="Clothing",
                name_ar="ملابس",
                name_fa="پوشاک",
            )
        )
        db.add(Category(id="cat-public", name_en="Shirts", name_ar="قمصان", name_fa="پیراهن"))
        db.add(StoreType(id="st-public", name_en="Fashion", name_ar="أزياء", name_fa="مد"))
        db.add(Brand(id="brand-public", code="public-brand", name_en="Nike", name_ar="نايك", name_fa="نایکی"))
        await db.flush()


async def _seed_product(
    db: AsyncSession,
    user: User,
    *,
    product_id: str,
    store_id: str,
    name_en: str,
    status: str = "active",
) -> None:
    await _ensure_shared_rows(db)

    db.add(
        Store(
            id=store_id,
            owner_id=user.id,
            name="Nike Store",
            category_id="cat-public",
            store_type_id="st-public",
            phone="+966500000000",
            address="Riyadh",
            location_lat=24.7,
            location_lng=46.7,
            country_code="SA",
            price_unit_code="SAR",
        )
    )
    product = StoreProduct(
        id=product_id,
        store_id=store_id,
        product_type_id="pt-public",
        category_id="cat-public",
        name_en=name_en,
        name_ar=name_en,
        name_fa=name_en,
        brand="brand-public",
        status=status,
        price=199.0,
        original_price=249.0,
        sale_price=179.0,
        currency="SAR",
    )
    db.add(product)
    await db.flush()
    db.add(ProductImage(product_id=product.id, image_url="product-graph/test.jpg", sort_order=0))
    await db.flush()


class TestRandomPublicProducts:
    async def test_random_products_public_no_auth(self, client: AsyncClient, test_user: User, db_session: AsyncSession) -> None:
        await _seed_product(db_session, test_user, product_id="rp-1", store_id="rp-store-1", name_en="Nike Air")
        await _seed_product(db_session, test_user, product_id="rp-2", store_id="rp-store-2", name_en="Nike Pro")

        resp = await client.get("/api/v1/public/products/random?limit=20")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

        by_id = {item["id"]: item for item in data}
        assert "rp-1" in by_id
        assert "rp-2" in by_id
        item = by_id["rp-1"]
        assert item["store_id"] == "rp-store-1"
        assert item["store_name"] == "Nike Store"
        assert item["name_en"] == "Nike Air"
        assert item["brand_name"] == "Nike"
        assert item["price"] == 199.0
        assert item["sale_price"] == 179.0
        assert item["currency"] == "SAR"
        assert item["status"] == "active"
        assert item["image_url"] == f"{settings.minio_public_url}/product-graph/test.jpg"

    async def test_random_products_include_all_statuses(self, client: AsyncClient, test_user: User, db_session: AsyncSession) -> None:
        await _seed_product(db_session, test_user, product_id="rp-active", store_id="rp-store-a", name_en="Active")
        await _seed_product(db_session, test_user, product_id="rp-draft", store_id="rp-store-d", name_en="Draft", status="draft")

        resp = await client.get("/api/v1/public/products/random")
        assert resp.status_code == 200
        data = resp.json()["data"]
        ids = {item["id"] for item in data}
        assert "rp-active" in ids
        assert "rp-draft" in ids

    async def test_random_products_limit_validation(self, client: AsyncClient, test_user: User, db_session: AsyncSession) -> None:
        await _seed_product(db_session, test_user, product_id="rp-v1", store_id="rp-store-v", name_en="Valid")

        resp = await client.get("/api/v1/public/products/random?limit=0")
        assert resp.status_code == 422
        resp = await client.get("/api/v1/public/products/random?limit=21")
        assert resp.status_code == 422
