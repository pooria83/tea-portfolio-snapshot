import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundError


class TestResolveImageUrl:
    def test_http_path_returns_as_is(self):
        from app.services.product_info_service import _resolve_image_url

        assert _resolve_image_url("https://cdn.example.com/img.jpg") == "https://cdn.example.com/img.jpg"

    def test_relative_path_prepends_minio_url(self):
        from app.services.product_info_service import _resolve_image_url

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.minio_public_url = "https://minio.example.com"
            result = _resolve_image_url("bucket/product/img.jpg")
            assert result == "https://minio.example.com/bucket/product/img.jpg"


class TestIsUuid:
    def test_valid_uuid(self):
        from app.repositories.catalog import _is_uuid

        assert _is_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_invalid_string(self):
        from app.repositories.catalog import _is_uuid

        assert _is_uuid("not-a-uuid") is False

    def test_empty_string(self):
        from app.repositories.catalog import _is_uuid

        assert _is_uuid("") is False

    def test_none_raises_attribute_error(self):
        from app.repositories.catalog import _is_uuid

        assert _is_uuid(None) is False  # type: ignore[arg-type]


class TestStripNulls:
    def test_dict_removes_nulls(self):
        from app.services.product_info_service import _strip_nulls

        result = _strip_nulls({"a": 1, "b": None, "c": {"d": None, "e": 2}})
        assert result == {"a": 1, "c": {"e": 2}}

    def test_list_removes_none_items(self):
        from app.services.product_info_service import _strip_nulls

        result = _strip_nulls([1, None, 2, None, 3])
        assert result == [1, 2, 3]

    def test_scalar_passthrough(self):
        from app.services.product_info_service import _strip_nulls

        assert _strip_nulls("hello") == "hello"
        assert _strip_nulls(42) == 42
        assert _strip_nulls(None) is None


class TestMinifyProductInfo:
    def test_extracts_sizes_from_variant_options(self):
        from app.services.product_info_service import minify_product_info

        data = {
            "variants": [{"options": ["S", "M"]}, {"options": ["M", "L"]}],
            "images": [],
            "pieces": [],
            "sizes": [],
            "name": "Test Product",
            "price": 100,
        }
        result = minify_product_info(data)
        assert result["available_sizes"] == ["S", "M", "L"]
        assert result["name"] == "Test Product"

    def test_extracts_image_alt_texts(self):
        from app.services.product_info_service import minify_product_info

        data = {
            "variants": [],
            "images": [{"alt_text": "Front view"}, {"alt_text": "Back view"}, {"alt_text": "Detail"}],
            "pieces": [],
            "sizes": [],
            "name": "Test",
        }
        result = minify_product_info(data)
        assert result["image_alt_texts"] == ["Front view", "Back view"]

    def test_strips_null_values(self):
        from app.services.product_info_service import minify_product_info

        data = {
            "variants": [],
            "images": [],
            "pieces": [],
            "sizes": [],
            "name": "Test",
            "description": None,
            "extra": {"inner": None},
        }
        result = minify_product_info(data)
        assert "description" not in result
        assert result["extra"] == {}

    def test_removes_list_fields(self):
        from app.services.product_info_service import minify_product_info

        data = {
            "variants": [{"options": ["M"]}],
            "images": [{"alt_text": "img"}],
            "pieces": [{"name": "piece1"}],
            "sizes": [{"label": "M"}],
            "name": "Test",
        }
        result = minify_product_info(data)
        assert "images" not in result
        assert "variants" not in result
        assert "pieces" not in result
        assert "sizes" not in result
        assert result["name"] == "Test"


class TestGetParentChain:
    async def test_single_level(self):
        from app.services.product_info_service import _get_parent_chain

        with patch("app.services.product_info_service.CategoryRepository") as mock_cls:
            mock_cls.return_value.get_chain = AsyncMock(return_value=[("cat-1", "Dresses", "فساتين", None)])
            chain = await _get_parent_chain(AsyncMock(), "cat-1", "en")
        assert chain == [{"id": "cat-1", "name": "Dresses"}]

    async def test_multi_level(self):
        from app.services.product_info_service import _get_parent_chain

        with patch("app.services.product_info_service.CategoryRepository") as mock_cls:
            mock_cls.return_value.get_chain = AsyncMock(
                return_value=[
                    ("cat-3", "Mini Dresses", "فساتين قصيرة", "cat-2"),
                    ("cat-2", "Dresses", "فساتين", "cat-1"),
                    ("cat-1", "Women", "نسائي", None),
                ]
            )
            chain = await _get_parent_chain(AsyncMock(), "cat-3", "en")
        assert chain == [
            {"id": "cat-3", "name": "Mini Dresses"},
            {"id": "cat-2", "name": "Dresses"},
            {"id": "cat-1", "name": "Women"},
        ]

    async def test_arabic_names(self):
        from app.services.product_info_service import _get_parent_chain

        with patch("app.services.product_info_service.CategoryRepository") as mock_cls:
            mock_cls.return_value.get_chain = AsyncMock(return_value=[("cat-1", "Dresses", "فساتين", None)])
            chain = await _get_parent_chain(AsyncMock(), "cat-1", "ar")
        assert chain == [{"id": "cat-1", "name": "فساتين"}]

    async def test_not_found_breaks_chain(self):
        from app.services.product_info_service import _get_parent_chain

        with patch("app.services.product_info_service.CategoryRepository") as mock_cls:
            mock_cls.return_value.get_chain = AsyncMock(return_value=[])
            chain = await _get_parent_chain(AsyncMock(), "nonexistent", "en")
        assert chain == []


class TestResolveAttrValue:
    async def test_empty_value(self):
        from app.services.product_info_service import _resolve_attr_value

        result = await _resolve_attr_value(AsyncMock(), "", "en")
        assert result is None

    async def test_plain_text(self):
        from app.services.product_info_service import _resolve_attr_value

        result = await _resolve_attr_value(AsyncMock(), "Cotton", "en")
        assert result == "Cotton"

    async def test_single_uuid(self):
        from app.services.product_info_service import _resolve_attr_value

        uid = "550e8400-e29b-41d4-a716-446655440000"
        with patch("app.services.product_info_service.AttributeOptionRepository") as mock_cls:
            mock_cls.return_value.get_localized_value = AsyncMock(return_value="Red")
            result = await _resolve_attr_value(AsyncMock(), uid, "en")
        assert result == "Red"

    async def test_single_uuid_not_found_returns_raw(self):
        from app.services.product_info_service import _resolve_attr_value

        uid = "550e8400-e29b-41d4-a716-446655440000"
        with patch("app.services.product_info_service.AttributeOptionRepository") as mock_cls:
            mock_cls.return_value.get_localized_value = AsyncMock(return_value=None)
            result = await _resolve_attr_value(AsyncMock(), uid, "en")
        assert result == uid

    async def test_multi_select_uuids(self):
        from app.services.product_info_service import _resolve_attr_value

        uuids = json.dumps(["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"])
        with patch("app.services.product_info_service.AttributeOptionRepository") as mock_cls:
            mock_cls.return_value.get_localized_value = AsyncMock(side_effect=["Red", "Blue"])
            result = await _resolve_attr_value(AsyncMock(), uuids, "en")
        assert result == ["Red", "Blue"]

    async def test_multi_select_some_not_found(self):
        from app.services.product_info_service import _resolve_attr_value

        uuids = json.dumps(["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"])
        with patch("app.services.product_info_service.AttributeOptionRepository") as mock_cls:
            mock_cls.return_value.get_localized_value = AsyncMock(side_effect=["Red", None])
            result = await _resolve_attr_value(AsyncMock(), uuids, "en")
        assert result == ["Red"]

    async def test_composition_material_percentage(self):
        from app.services.product_info_service import _resolve_attr_value

        composition = json.dumps([{"material": "550e8400-e29b-41d4-a716-446655440000", "percentage": 80}])
        with patch("app.services.product_info_service.AttributeOptionRepository") as mock_cls:
            mock_cls.return_value.get_localized_value = AsyncMock(return_value="Cotton")
            result = await _resolve_attr_value(AsyncMock(), composition, "en")
        assert result == [{"material": "Cotton", "percentage": 80}]


_BASE_MAPPING = {
    "id": "prod-1",
    "name_en": "Test Product",
    "name_ar": "منتج تجريبي",
    "name_fa": "محصول آزمایشی",
    "short_description_en": "Short desc",
    "short_description_ar": None,
    "short_description_fa": None,
    "long_description_en": "Long desc",
    "long_description_ar": None,
    "long_description_fa": None,
    "ai_description_en": "AI desc",
    "ai_description_ar": None,
    "ai_description_fa": None,
    "brand": None,
    "slug": "test-product",
    "sku": "TP-001",
    "barcode": "123456",
    "status": "active",
    "has_variants": False,
    "is_multi_piece": False,
    "price": 99.99,
    "original_price": 129.99,
    "sale_price": None,
    "currency": "SAR",
    "quantity": 10,
    "low_stock_threshold": 2,
    "weight": 0.5,
    "weight_unit": "kg",
    "collection": "Summer 2024",
    "collection_ar": None,
    "collection_fa": None,
    "country_of_origin": "SA",
    "care_instructions_en": "Dry clean",
    "care_instructions_ar": None,
    "care_instructions_fa": None,
    "model_height": None,
    "model_wears_size": None,
    "video_url": None,
    "source_url": None,
    "meta_title_en": None,
    "meta_title_ar": None,
    "meta_title_fa": None,
    "meta_description_en": None,
    "meta_description_ar": None,
    "meta_description_fa": None,
    "category_id": None,
    "product_type_id": None,
    "created_at": None,
    "updated_at": None,
}


class TestGetProductInfo:
    async def test_product_not_found(self):
        from app.services.product_info_service import get_product_info

        with patch("app.services.product_info_service.StoreProductRepository") as mock_cls:
            mock_cls.return_value.get_info_row = AsyncMock(return_value=None)
            with pytest.raises(NotFoundError):
                await get_product_info(AsyncMock(), "nonexistent", "en")

    async def test_basic_product_info(self):
        from app.services.product_info_service import get_product_info

        with (
            patch("app.services.product_info_service.StoreProductRepository") as sp,
            patch("app.services.product_info_service.ProductImageRepository") as im,
            patch("app.services.product_info_service.AttributeRepository") as at,
            patch("app.services.product_info_service.ProductSizeRepository") as sz,
            patch("app.services.product_info_service.ProductVariantRepository") as vr,
            patch("app.services.product_info_service.ProductPieceRepository") as pc,
        ):
            sp.return_value.get_info_row = AsyncMock(return_value=dict(_BASE_MAPPING))
            im.return_value.list_info_rows = AsyncMock(return_value=[])
            at.return_value.list_value_rows_for_product = AsyncMock(return_value=[])
            sz.return_value.list_info_rows = AsyncMock(return_value=[])
            vr.return_value.list_info_rows = AsyncMock(return_value=[])
            pc.return_value.list_info_rows = AsyncMock(return_value=[])

            result = await get_product_info(AsyncMock(), "prod-1", "en")

        assert result["id"] == "prod-1"
        assert result["name"] == "Test Product"
        assert result["price"] == 99.99
        assert result["currency"] == "SAR"
        assert result["brand"] is None
        assert result["category"] is None
        assert result["product_type"] is None
        assert result["images"] == []
        assert result["attributes"] == []
        assert result["sizes"] == []
        assert result["variants"] == []
        assert result["pieces"] == []
        assert result["created_at"] is None
        assert result["updated_at"] is None

    async def test_with_brand_category_type(self):
        from app.services.product_info_service import get_product_info

        row = dict(_BASE_MAPPING)
        row.update(
            {
                "id": "prod-2",
                "name_en": "Silk Dress",
                "name_ar": "فستان حريري",
                "name_fa": "لباس ابریشمی",
                "brand": "brand-zara",
                "has_variants": True,
                "category_id": "cat-1",
                "product_type_id": "pt-1",
            }
        )
        with (
            patch("app.services.product_info_service.StoreProductRepository") as sp,
            patch("app.services.product_info_service.BrandRepository") as br,
            patch("app.services.product_info_service.CategoryRepository") as cr,
            patch("app.services.product_info_service.ProductTypeRepository") as ptr,
            patch("app.services.product_info_service.ProductImageRepository") as im,
            patch("app.services.product_info_service.AttributeRepository") as at,
            patch("app.services.product_info_service.ProductSizeRepository") as sz,
            patch("app.services.product_info_service.ProductVariantRepository") as vr,
            patch("app.services.product_info_service.ProductPieceRepository") as pc,
        ):
            sp.return_value.get_info_row = AsyncMock(return_value=row)
            br.return_value.get_name = AsyncMock(return_value="Zara")
            cr.return_value.get_chain = AsyncMock(return_value=[("cat-1", "Dresses", "فساتين", None)])
            ptr.return_value.get_name = AsyncMock(return_value="Clothing")
            im.return_value.list_info_rows = AsyncMock(return_value=[])
            at.return_value.list_value_rows_for_product = AsyncMock(return_value=[])
            sz.return_value.list_info_rows = AsyncMock(return_value=[])
            vr.return_value.list_info_rows = AsyncMock(return_value=[])
            pc.return_value.list_info_rows = AsyncMock(return_value=[])

            result = await get_product_info(AsyncMock(), "prod-2", "en")

        assert result["id"] == "prod-2"
        assert result["brand"] == "Zara"
        assert result["category"] == {"id": "cat-1", "name": "Dresses"}
        assert result["product_type"] == "Clothing"
        assert result["category_parents"] == []

    async def test_with_images(self):
        from app.services.product_info_service import get_product_info

        row = dict(_BASE_MAPPING)
        row["id"] = "prod-3"
        img1 = SimpleNamespace(
            id="img-1",
            image_url="bucket/img1.jpg",
            alt_text_en="Front view",
            alt_text_ar=None,
            alt_text_fa=None,
            is_video=False,
            sort_order=1,
            view_type_name="default",
        )
        img2 = SimpleNamespace(
            id="img-2",
            image_url="bucket/img2.jpg",
            alt_text_en="Back view",
            alt_text_ar=None,
            alt_text_fa=None,
            is_video=False,
            sort_order=2,
            view_type_name="default",
        )
        with (
            patch("app.services.product_info_service.StoreProductRepository") as sp,
            patch("app.services.product_info_service.ProductImageRepository") as im,
            patch("app.services.product_info_service.AttributeRepository") as at,
            patch("app.services.product_info_service.ProductSizeRepository") as sz,
            patch("app.services.product_info_service.ProductVariantRepository") as vr,
            patch("app.services.product_info_service.ProductPieceRepository") as pc,
            patch("app.services.product_info_service._resolve_image_url") as mock_resolve,
        ):
            sp.return_value.get_info_row = AsyncMock(return_value=row)
            im.return_value.list_info_rows = AsyncMock(return_value=[img1, img2])
            at.return_value.list_value_rows_for_product = AsyncMock(return_value=[])
            sz.return_value.list_info_rows = AsyncMock(return_value=[])
            vr.return_value.list_info_rows = AsyncMock(return_value=[])
            pc.return_value.list_info_rows = AsyncMock(return_value=[])
            mock_resolve.side_effect = lambda p: f"https://cdn.example.com/{p}"

            result = await get_product_info(AsyncMock(), "prod-3", "en")

        images = cast("list[dict[str, object]]", result["images"])
        assert len(images) == 2
        assert images[0]["url"] == "https://cdn.example.com/bucket/img1.jpg"
        assert images[1]["alt_text"] == "Back view"

    async def test_with_variants(self):
        from app.services.product_info_service import get_product_info

        row = dict(_BASE_MAPPING)
        row.update(
            {
                "id": "prod-4",
                "has_variants": True,
                "price": 100,
                "original_price": 150,
                "quantity": 0,
                "currency": "SAR",
            }
        )
        v1 = SimpleNamespace(id="var-1", sku="VAR-RED-M", price=100, original_price=150, sale_price=None, quantity=5, is_active=True, sort_order=1)
        with (
            patch("app.services.product_info_service.StoreProductRepository") as sp,
            patch("app.services.product_info_service.ProductImageRepository") as im,
            patch("app.services.product_info_service.AttributeRepository") as at,
            patch("app.services.product_info_service.ProductSizeRepository") as sz,
            patch("app.services.product_info_service.ProductVariantRepository") as vr,
            patch("app.services.product_info_service.ProductPieceRepository") as pc,
            patch("app.services.product_info_service._resolve_image_url") as mock_resolve,
        ):
            sp.return_value.get_info_row = AsyncMock(return_value=row)
            im.return_value.list_info_rows = AsyncMock(return_value=[])
            im.return_value.list_urls_by_variant = AsyncMock(return_value=["path/img.jpg"])
            at.return_value.list_value_rows_for_product = AsyncMock(return_value=[])
            sz.return_value.list_info_rows = AsyncMock(return_value=[])
            vr.return_value.list_info_rows = AsyncMock(return_value=[v1])
            vr.return_value.list_option_names = AsyncMock(return_value=["Red", "M"])
            pc.return_value.list_info_rows = AsyncMock(return_value=[])
            mock_resolve.return_value = "https://cdn.example.com/img.jpg"

            result = await get_product_info(AsyncMock(), "prod-4", "en")

        variants = cast("list[dict[str, object]]", result["variants"])
        assert len(variants) == 1
        v = variants[0]
        assert v["sku"] == "VAR-RED-M"
        assert v["options"] == ["Red", "M"]
        assert v["discount_percentage"] == 33
        assert v["images"] == ["https://cdn.example.com/img.jpg"]

    async def test_arabic_fields(self):
        from app.services.product_info_service import get_product_info

        row = dict(_BASE_MAPPING)
        row.update(
            {
                "id": "prod-ar",
                "name_ar": "منتج تجريبي",
                "short_description_ar": "وصف قصير",
                "long_description_ar": "وصف طويل",
                "ai_description_ar": "وصف ذكي",
                "collection_ar": "مجموعة صيف ٢٠٢٤",
                "care_instructions_ar": "تعليمات العناية",
            }
        )
        with (
            patch("app.services.product_info_service.StoreProductRepository") as sp,
            patch("app.services.product_info_service.ProductImageRepository") as im,
            patch("app.services.product_info_service.AttributeRepository") as at,
            patch("app.services.product_info_service.ProductSizeRepository") as sz,
            patch("app.services.product_info_service.ProductVariantRepository") as vr,
            patch("app.services.product_info_service.ProductPieceRepository") as pc,
        ):
            sp.return_value.get_info_row = AsyncMock(return_value=row)
            im.return_value.list_info_rows = AsyncMock(return_value=[])
            at.return_value.list_value_rows_for_product = AsyncMock(return_value=[])
            sz.return_value.list_info_rows = AsyncMock(return_value=[])
            vr.return_value.list_info_rows = AsyncMock(return_value=[])
            pc.return_value.list_info_rows = AsyncMock(return_value=[])

            result = await get_product_info(AsyncMock(), "prod-ar", "ar")

        assert result["short_description"] == "وصف قصير"
        assert result["long_description"] == "وصف طويل"
        assert result["ai_description"] == "وصف ذكي"
        assert result["collection"] == "مجموعة صيف ٢٠٢٤"
        assert result["care_instructions"] == "تعليمات العناية"
