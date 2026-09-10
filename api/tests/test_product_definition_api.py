import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import create_access_token
from app.core.password import hash_password
from app.models.attribute import Attribute
from app.models.attribute_group import AttributeGroup
from app.models.attribute_option import AttributeOption
from app.models.brand import Brand
from app.models.category import Category
from app.models.product_type import ProductType
from app.models.product_type_attribute import ProductTypeAttribute
from app.models.product_type_image_view_type import ProductTypeImageViewType
from app.models.product_variant import ProductVariant
from app.models.store import Store
from app.models.store_type import StoreType
from app.models.user import User


def _opt(name_en: str, color_hex: str | None = None) -> dict:
    return {"value_en": name_en, "value_ar": name_en, "value_fa": name_en, "color_hex": color_hex, "sort_order": 0}


_SEED_PT_ID = "pt-clothing"

_SEED_OPTIONS: list[dict] = [
    {"id": "opt-red", **{"attribute_id": "attr-primary-color", **_opt("Red", "#FF0000")}},
    {"id": "opt-blue", **{"attribute_id": "attr-primary-color", **_opt("Blue", "#0000FF")}},
    {"id": "opt-slim", **{"attribute_id": "attr-fit-type", **_opt("Slim")}},
    {"id": "opt-regular", **{"attribute_id": "attr-fit-type", **_opt("Regular")}},
]

_SEED_CAT_ID = "cat-shirts"

_SEED_BRAND_ID = "brand-nike"


async def _seed_db(db: AsyncSession, user_id: str) -> Store:
    db.add(AttributeGroup(id="grp-fit", code="fit", name_en="Fit & Size", name_ar="Fit & Size", name_fa="Fit & Size", sort_order=0))
    await db.flush()

    db.add(
        Attribute(
            id="attr-primary-color",
            code="primary_color",
            name_en="Primary Color",
            name_ar="Primary Color",
            name_fa="Primary Color",
            value_type="string",
            group_id="grp-fit",
            input_type="multi-select",
            is_variant_defining=True,
            validation_rules={"required": {"en": "Required", "ar": "Required", "fa": "Required"}},
            sort_order=0,
        )
    )
    db.add(
        Attribute(
            id="attr-fit-type",
            code="fit_type",
            name_en="Fit Type",
            name_ar="Fit Type",
            name_fa="Fit Type",
            value_type="string",
            group_id="grp-fit",
            input_type="multi-select",
            is_variant_defining=True,
            validation_rules={"required": {"en": "Required", "ar": "Required", "fa": "Required"}},
            sort_order=1,
        )
    )
    await db.flush()

    for opt_data in _SEED_OPTIONS:
        db.add(AttributeOption(**opt_data))
    await db.flush()

    pt = ProductType(id=_SEED_PT_ID, code="clothing", name_en="Clothing", name_ar="ملابس", name_fa="لباس", sort_order=0)
    db.add(pt)
    await db.flush()

    db.add(ProductTypeAttribute(product_type_id=_SEED_PT_ID, attribute_id="attr-primary-color", sort_order=0))
    db.add(ProductTypeAttribute(product_type_id=_SEED_PT_ID, attribute_id="attr-fit-type", sort_order=1))
    await db.flush()

    cat = Category(id=_SEED_CAT_ID, product_type_id=_SEED_PT_ID, name_en="Shirts", name_ar="Shirts", name_fa="Shirts", sort_order=0, is_active=True)
    db.add(cat)
    await db.flush()

    brand = Brand(id=_SEED_BRAND_ID, code="nike", name_en="Nike", name_ar="Nike", name_fa="Nike", sort_order=0)
    db.add(brand)
    await db.flush()

    vt = ProductTypeImageViewType(id=str(uuid.uuid4()), code="main", product_type_id=_SEED_PT_ID, name_en="Main", name_ar="Main", name_fa="Main", sort_order=0)
    db.add(vt)
    await db.flush()

    st = StoreType(id=str(uuid.uuid4()), name_en="Retail", name_ar="Retail", name_fa="Retail", is_active=True)
    db.add(st)
    await db.flush()

    store = Store(
        id=str(uuid.uuid4()),
        owner_id=user_id,
        name="Test Store",
        category_id=_SEED_CAT_ID,
        store_type_id=st.id,
        phone="+966500000000",
        address="Test Address",
        location_lat=24.7136,
        location_lng=46.6753,
        country_code="KW",
        price_unit_code="KWD",
        is_active=True,
    )
    db.add(store)
    await db.flush()

    return store


class TestPublicReadEndpoints:
    """Test the public GET endpoints (no auth required)."""

    @pytest.mark.asyncio
    async def test_list_product_types(self, client: AsyncClient, db_session: AsyncSession):
        pt = ProductType(id="pt-test-list", code="test", name_en="Test", name_ar="Test", name_fa="Test", sort_order=0)
        db_session.add(pt)
        await db_session.flush()

        resp = await client.get("/api/v1/products/types")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]
        ids = [t["id"] for t in data["data"]]
        assert "pt-test-list" in ids

    @pytest.mark.asyncio
    async def test_get_product_type_detail(self, client: AsyncClient, db_session: AsyncSession):
        pt = ProductType(id="pt-detail", code="detail", name_en="Detail", name_ar="Detail", name_fa="Detail", sort_order=0)
        db_session.add(pt)
        db_session.add(AttributeGroup(id="grp-detail", code="detail", name_en="D", name_ar="D", name_fa="D", sort_order=0))
        attr = Attribute(id="attr-detail", code="color", name_en="Color", name_ar="Color", name_fa="Color", value_type="string", input_type="select", group_id="grp-detail", sort_order=0)
        db_session.add(attr)
        db_session.add(ProductTypeAttribute(product_type_id="pt-detail", attribute_id="attr-detail", sort_order=0))
        await db_session.flush()

        resp = await client.get("/api/v1/products/types/pt-detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["id"] == "pt-detail"
        assert len(data["data"]["attributes"]) == 1

    @pytest.mark.asyncio
    async def test_list_categories(self, client: AsyncClient, db_session: AsyncSession):
        pt = ProductType(id="pt-cat", code="cat", name_en="Cat", name_ar="Cat", name_fa="Cat", sort_order=0)
        db_session.add(pt)
        cat = Category(id="cat-root", product_type_id="pt-cat", name_en="Root", name_ar="Root", name_fa="Root", sort_order=0, is_active=True)
        db_session.add(cat)
        await db_session.flush()

        resp = await client.get("/api/v1/products/categories?product_type_id=pt-cat")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["id"] == "cat-root"

    @pytest.mark.asyncio
    async def test_list_attribute_groups(self, client: AsyncClient, db_session: AsyncSession):
        db_session.add(AttributeGroup(id="grp-list", code="list", name_en="List", name_ar="List", name_fa="List", sort_order=0))
        await db_session.flush()

        resp = await client.get("/api/v1/products/attribute-groups")
        assert resp.status_code == 200
        assert any(g["id"] == "grp-list" for g in resp.json()["data"])

    @pytest.mark.asyncio
    async def test_list_attributes_by_type(self, client: AsyncClient, db_session: AsyncSession):
        pt = ProductType(id="pt-attr-list", code="attr-list", name_en="AL", name_ar="AL", name_fa="AL", sort_order=0)
        db_session.add(pt)
        db_session.add(AttributeGroup(id="grp-al", code="al", name_en="AL", name_ar="AL", name_fa="AL", sort_order=0))
        attr = Attribute(id="attr-al", code="size", name_en="Size", name_ar="Size", name_fa="Size", value_type="string", input_type="select", group_id="grp-al", sort_order=0)
        db_session.add(attr)
        db_session.add(ProductTypeAttribute(product_type_id="pt-attr-list", attribute_id="attr-al", sort_order=0))
        await db_session.flush()

        resp = await client.get("/api/v1/products/attributes?product_type_id=pt-attr-list")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["id"] == "attr-al"

    @pytest.mark.asyncio
    async def test_list_brands(self, client: AsyncClient, db_session: AsyncSession):
        db_session.add(Brand(id="brand-test", code="test", name_en="TestBrand", name_ar="TestBrand", name_fa="TestBrand", sort_order=0))
        await db_session.flush()

        resp = await client.get("/api/v1/products/brands")
        assert resp.status_code == 200
        assert any(b["id"] == "brand-test" for b in resp.json()["data"])


class TestStoreProductCRUD:
    @pytest.mark.asyncio
    async def test_create_product_minimal(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        payload = {
            "product_type_id": _SEED_PT_ID,
            "status": "active",
            "name_en": "Test Product",
            "price": 49.99,
        }

        resp = await client.post(f"/api/v1/stores/{store.id}/products", json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["name_en"] == "Test Product"
        assert data["price"] == 49.99
        assert data["has_variants"] is False

    @pytest.mark.asyncio
    async def test_create_product_with_variants(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        payload = {
            "product_type_id": _SEED_PT_ID,
            "status": "active",
            "name_en": "Variant Product",
            "price": 59.99,
            "attribute_values": [],
            "variants": [
                {
                    "sku": "RED-SLIM",
                    "price": 49.99,
                    "quantity": 10,
                    "is_active": True,
                    "attribute_option_ids": ["opt-red", "opt-slim"],
                },
                {
                    "sku": "BLUE-REG",
                    "price": 59.99,
                    "quantity": 5,
                    "is_active": True,
                    "attribute_option_ids": ["opt-blue", "opt-regular"],
                },
            ],
            "images": [],
        }

        resp = await client.post(f"/api/v1/stores/{store.id}/products", json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["has_variants"] is True
        assert len(data["variants"]) == 2

    @pytest.mark.asyncio
    async def test_create_product_inactive_variant_no_price(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        payload = {
            "product_type_id": _SEED_PT_ID,
            "status": "active",
            "name_en": "Inactive Variant",
            "price": 29.99,
            "attribute_values": [],
            "variants": [
                {
                    "sku": "RED-SLIM-INACTIVE",
                    "price": None,
                    "quantity": 0,
                    "is_active": False,
                    "attribute_option_ids": ["opt-red", "opt-slim"],
                },
            ],
            "images": [],
        }

        resp = await client.post(f"/api/v1/stores/{store.id}/products", json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        assert len(resp.json()["data"]["variants"]) == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_product_returns_404(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        resp = await client.get(f"/api/v1/stores/{store.id}/products/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_product_public_no_auth(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        create_resp = await client.post(
            f"/api/v1/stores/{store.id}/products",
            json={"product_type_id": _SEED_PT_ID, "status": "active", "name_en": "Public Product", "price": 10.0},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        product_id = create_resp.json()["data"]["id"]

        resp = await client.get(f"/api/v1/stores/{store.id}/products/{product_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["id"] == product_id
        assert data["name_en"] == "Public Product"

    @pytest.mark.asyncio
    async def test_get_product_non_owner_can_access(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        create_resp = await client.post(
            f"/api/v1/stores/{store.id}/products",
            json={"product_type_id": _SEED_PT_ID, "status": "active", "name_en": "Owner Product", "price": 20.0},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        product_id = create_resp.json()["data"]["id"]

        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password=hash_password("OtherPass123!"),
            full_name="Other User",
            role="user",
        )
        db_session.add(other_user)
        await db_session.flush()
        other_headers = {"Authorization": f"Bearer {create_access_token(other_user.id, other_user.role)}"}

        resp = await client.get(f"/api/v1/stores/{store.id}/products/{product_id}", headers=other_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == product_id

    @pytest.mark.asyncio
    async def test_update_product_merge_variants(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        create_payload = {
            "product_type_id": _SEED_PT_ID,
            "status": "active",
            "name_en": "Merge Test",
            "price": 30.0,
            "attribute_values": [],
            "variants": [
                {"sku": "RED-SLIM", "price": 30.0, "quantity": 5, "is_active": True, "attribute_option_ids": ["opt-red", "opt-slim"]},
                {"sku": "BLUE-REG", "price": 35.0, "quantity": 3, "is_active": True, "attribute_option_ids": ["opt-blue", "opt-regular"]},
            ],
            "images": [],
        }
        create_resp = await client.post(f"/api/v1/stores/{store.id}/products", json=create_payload, headers=auth_headers)
        assert create_resp.status_code == 201, create_resp.text
        product_id = create_resp.json()["data"]["id"]

        update_payload = {
            "name_en": "Merge Test Updated",
            "price": 35.0,
            "variants": [
                {"sku": "RED-SLIM-UPDATED", "price": 32.0, "quantity": 10, "is_active": True, "attribute_option_ids": ["opt-red", "opt-slim"]},
                {"sku": "BLUE-REG-UPDATED", "price": 38.0, "quantity": 7, "is_active": True, "attribute_option_ids": ["opt-blue", "opt-regular"]},
                {"sku": "NEW-RED-REG", "price": 40.0, "quantity": 2, "is_active": True, "attribute_option_ids": ["opt-red", "opt-regular"]},
            ],
        }
        update_resp = await client.put(f"/api/v1/stores/{store.id}/products/{product_id}", json=update_payload, headers=auth_headers)
        assert update_resp.status_code == 200, update_resp.text
        data = update_resp.json()["data"]
        assert data["name_en"] == "Merge Test Updated"
        assert data["price"] == 35.0

        # Verify via DB direct query
        db_stmt = select(ProductVariant.sku).where(ProductVariant.product_id == product_id)
        db_r = await db_session.execute(db_stmt)
        db_skus = {row[0] for row in db_r.all()}
        assert "RED-SLIM" not in db_skus, f"DB still has RED-SLIM in {db_skus}"
        assert "RED-SLIM-UPDATED" in db_skus, f"DB missing RED-SLIM-UPDATED in {db_skus}"
        assert len(db_skus) == 3, f"DB has {len(db_skus)} variants: {db_skus}"

        variant_skus = {v["sku"] for v in data["variants"]}
        assert "RED-SLIM-UPDATED" in variant_skus, f"Missing RED-SLIM-UPDATED in {variant_skus}"
        assert "BLUE-REG-UPDATED" in variant_skus, f"Missing BLUE-REG-UPDATED in {variant_skus}"
        assert "NEW-RED-REG" in variant_skus, f"Missing NEW-RED-REG in {variant_skus}"
        assert "RED-SLIM" not in variant_skus, f"RED-SLIM should have been removed but found in {variant_skus}"
        assert len(data["variants"]) == 3, f"Expected 3 variants, got {len(data['variants'])}: {variant_skus}"

    @pytest.mark.asyncio
    async def test_delete_product(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        payload = {"product_type_id": _SEED_PT_ID, "status": "active", "name_en": "To Delete", "price": 10.0}
        create_resp = await client.post(f"/api/v1/stores/{store.id}/products", json=payload, headers=auth_headers)
        product_id = create_resp.json()["data"]["id"]

        delete_resp = await client.delete(f"/api/v1/stores/{store.id}/products/{product_id}", headers=auth_headers)
        assert delete_resp.status_code == 200

        get_resp = await client.get(f"/api/v1/stores/{store.id}/products/{product_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_store_products(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        for i in range(3):
            payload = {"product_type_id": _SEED_PT_ID, "status": "active", "name_en": f"Product {i}", "price": float(10 + i)}
            await client.post(f"/api/v1/stores/{store.id}/products", json=payload, headers=auth_headers)

        resp = await client.get(f"/api/v1/stores/{store.id}/products", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 3

    @pytest.mark.asyncio
    async def test_create_product_with_image(self, client: AsyncClient, db_session: AsyncSession, test_user, auth_headers):
        store = await _seed_db(db_session, test_user.id)

        from app.models.product_type_image_view_type import ProductTypeImageViewType as VTModel

        vt = VTModel(id=str(uuid.uuid4()), code="testvt", product_type_id=_SEED_PT_ID, name_en="TestVT", name_ar="TestVT", name_fa="TestVT", sort_order=0)
        db_session.add(vt)
        await db_session.flush()

        payload = {
            "product_type_id": _SEED_PT_ID,
            "status": "active",
            "name_en": "Image Product",
            "price": 25.0,
            "images": [{"image_url": "https://example.com/img.jpg", "view_type_id": vt.id}],
        }

        resp = await client.post(f"/api/v1/stores/{store.id}/products", json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        assert len(resp.json()["data"]["images"]) == 1

    @pytest.mark.asyncio
    async def test_categories_tree_all_no_filter(self, client: AsyncClient, db_session: AsyncSession):
        pt = ProductType(id="pt-cat-all", code="cat-all", name_en="CA", name_ar="CA", name_fa="CA", sort_order=0)
        db_session.add(pt)
        cat = Category(id="cat-all-root", product_type_id="pt-cat-all", name_en="AllRoot", name_ar="AllRoot", name_fa="AllRoot", sort_order=0, is_active=True)
        db_session.add(cat)
        await db_session.flush()

        resp = await client.get("/api/v1/products/categories")
        assert resp.status_code == 200
        assert any(c["id"] == "cat-all-root" for c in resp.json()["data"])

    @pytest.mark.asyncio
    async def test_attribute_groups_with_product_type_filter(self, client: AsyncClient, db_session: AsyncSession):
        resp = await client.get(f"/api/v1/products/attribute-groups?product_type_id={_SEED_PT_ID}")
        assert resp.status_code == 200
