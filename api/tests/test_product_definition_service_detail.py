from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.attribute import Attribute


@pytest.mark.asyncio
async def test_get_product_type_detail_success():
    with patch("app.services.product_definition_service.ProductTypeRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        pt = MagicMock()
        pt.id = "pt-1"
        pt.code = "test"
        pt.name_ar = "Test"
        pt.name_en = "Test"
        pt.name_fa = "Test"
        pt.icon = "icon"
        pt.sort_order = 1
        pta = MagicMock()
        pta.attribute = MagicMock()
        pt.product_type_attributes = [pta]
        mock_repo.get_with_attributes.return_value = pt
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_product_type_detail

        result = await get_product_type_detail(AsyncMock(), "pt-1")
        assert result["id"] == "pt-1"
        assert len(result["attributes"]) == 1
        mock_repo.get_with_attributes.assert_called_once_with("pt-1")


@pytest.mark.asyncio
async def test_get_attribute_groups_with_product_type():
    with patch("app.services.product_definition_service.AttributeGroupRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_by_product_type_dto.return_value = [{"id": "grp-1"}, {"id": "grp-2"}]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_attribute_groups

        result = await get_attribute_groups(AsyncMock(), product_type_id="pt-1")
        assert len(result) == 2
        mock_repo.list_by_product_type_dto.assert_called_once_with("pt-1")


@pytest.mark.asyncio
async def test_list_store_products():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_by_store.return_value = [MagicMock(), MagicMock()]
        mock_repo.count_by_store.return_value = 5
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import list_store_products

        items, total = await list_store_products(AsyncMock(), "store-1", skip=0, limit=10)
        assert len(items) == 2
        assert total == 5
        mock_repo.list_by_store.assert_called_once_with("store-1", skip=0, limit=10)
        mock_repo.count_by_store.assert_called_once_with("store-1")


@pytest.mark.asyncio
async def test_get_store_product_success():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.id = "product-1"
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get_with_all.return_value = product
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_store_product

        result = await get_store_product(AsyncMock(), "product-1", "store-1")
        assert result.id == "product-1"


@pytest.mark.asyncio
async def test_delete_store_product_wrong_store():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "other-store"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import delete_store_product

        with pytest.raises(NotFoundError, match="Product not found"):
            await delete_store_product(AsyncMock(), "product-1", "store-1")


@pytest.mark.asyncio
async def test_add_product_image_success():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.id = "product-1"
        product.store_id = "store-1"
        product.images = []
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)

        from app.services.product_definition_service import add_product_image

        result = await add_product_image(mock_db, "product-1", "store-1", "http://example.com/img.jpg", view_type_id="vt-1")
        assert result.image_url == "img.jpg"
        assert result.view_type_id == "vt-1"
        assert result.sort_order == 0


@pytest.mark.asyncio
async def test_update_product_image_success():
    mock_db = AsyncMock(spec=AsyncSession)
    image = MagicMock()
    image.id = "img-1"
    image.sort_order = 0
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = image
    mock_db.execute.return_value = mock_result

    from app.services.product_definition_service import update_product_image

    result = await update_product_image(mock_db, "img-1", "store-1", sort_order=2, alt_text_en="New alt")
    assert result.sort_order == 2


@pytest.mark.asyncio
async def test_update_product_image_not_found():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    from app.services.product_definition_service import update_product_image

    with pytest.raises(NotFoundError, match="Image not found"):
        await update_product_image(mock_db, "nonexistent", "store-1")


@pytest.mark.asyncio
async def test_delete_product_image_success():
    mock_db = AsyncMock(spec=AsyncSession)
    image = MagicMock()
    image.id = "img-1"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = image
    mock_db.execute.return_value = mock_result

    from app.services.product_definition_service import delete_product_image

    await delete_product_image(mock_db, "img-1", "store-1")
    mock_db.delete.assert_called_once_with(image)
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_product_image_not_found():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    from app.services.product_definition_service import delete_product_image

    with pytest.raises(NotFoundError, match="Image not found"):
        await delete_product_image(mock_db, "nonexistent", "store-1")


@pytest.mark.asyncio
async def test_reorder_product_images():
    mock_db = AsyncMock(spec=AsyncSession)
    img1 = MagicMock()
    img1.id = "img-1"
    img2 = MagicMock()
    img2.id = "img-2"
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [img1, img2]
    mock_db.execute.return_value = mock_result

    from app.services.product_definition_service import reorder_product_images

    await reorder_product_images(mock_db, "store-1", ["img-2", "img-1"])
    assert img1.sort_order == 1
    assert img2.sort_order == 0


@pytest.mark.asyncio
async def test_create_store_product_with_pieces_and_color_sets():
    with (
        patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls,
        patch("app.services.product_definition_service._resolve_attribute_values") as mock_resolve,
        patch("app.services.product_definition_service._create_variant") as mock_create_variant,
    ):
        mock_repo = AsyncMock()
        product = MagicMock()
        product.id = "product-1"
        mock_repo.add.return_value = product
        mock_repo_cls.return_value = mock_repo
        mock_resolve.return_value = []
        mock_create_variant.return_value = MagicMock(id="variant-1")

        from app.schemas.product_definition import (
            ProductColorSetInput,
            ProductColorSetValueInput,
            ProductImageInput,
            ProductPieceInput,
            ProductSizeInput,
            StoreProductCreate,
        )

        data = StoreProductCreate(
            product_type_id="pt-1",
            status="active",
            name_en="Multi Piece Product",
            price=100.0,
            pieces=[
                ProductPieceInput(name_en="Top", name_ar="Top"),
                ProductPieceInput(name_en="Bottom", name_ar="Bottom"),
            ],
            color_sets=[
                ProductColorSetInput(
                    sort_order=0,
                    values=[
                        ProductColorSetValueInput(piece_id="0", color_option_id="opt-red"),
                    ],
                ),
            ],
            sizes=[
                ProductSizeInput(size_label="M", size_system="general", stock=5, sort_order=0),
            ],
            images=[
                ProductImageInput(image_url="http://example.com/img.jpg", view_type_id="vt-1", sort_order=0),
            ],
            variants=[],
        )

        mock_db = AsyncMock(spec=AsyncSession)

        from app.services.product_definition_service import create_store_product

        result = await create_store_product(mock_db, "store-1", data)
        assert result.id == "product-1"


@pytest.mark.asyncio
async def test_create_store_product_with_variants_and_images():
    with (
        patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls,
        patch("app.services.product_definition_service._resolve_attribute_values") as mock_resolve,
        patch("app.services.product_definition_service._create_variant") as mock_create_variant,
    ):
        v1 = MagicMock(id="variant-1")
        v2 = MagicMock(id="variant-2")
        mock_repo = AsyncMock()
        product = MagicMock()
        product.id = "product-1"
        mock_repo.add.return_value = product
        mock_repo_cls.return_value = mock_repo
        mock_resolve.return_value = []
        mock_create_variant.side_effect = [v1, v2]

        from app.schemas.product_definition import (
            ProductImageInput,
            ProductVariantCreate,
            StoreProductCreate,
        )

        data = StoreProductCreate(
            product_type_id="pt-1",
            status="active",
            name_en="Variant Product",
            price=50.0,
            pieces=[],
            color_sets=[],
            variants=[
                ProductVariantCreate(sku="V1", price=50.0, quantity=5, is_active=True, attribute_option_ids=["opt-red"]),
                ProductVariantCreate(sku="V2", price=60.0, quantity=3, is_active=True, attribute_option_ids=["opt-blue"]),
            ],
            images=[
                ProductImageInput(image_url="http://example.com/img1.jpg", view_type_id="vt-1", variant_signature=["opt-red"], sort_order=0),
                ProductImageInput(image_url="http://example.com/img2.jpg", view_type_id="vt-1", variant_index=1, sort_order=1),
            ],
            sizes=[],
        )

        mock_db = AsyncMock(spec=AsyncSession)

        from app.services.product_definition_service import create_store_product

        result = await create_store_product(mock_db, "store-1", data)
        assert result.id == "product-1"


@pytest.mark.asyncio
async def test_update_store_product_full():
    with (
        patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls,
        patch("app.services.product_definition_service._resolve_attribute_values") as mock_resolve,
        patch("app.services.product_definition_service._merge_variants") as mock_merge,
        patch("app.services.product_definition_service._update_product_images"),
    ):
        product = MagicMock()
        product.id = "product-1"
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo
        mock_resolve.return_value = []
        mock_merge.return_value = []

        from app.schemas.product_definition import (
            ProductColorSetInput,
            ProductColorSetValueInput,
            ProductPieceInput,
            ProductSizeInput,
            StoreProductUpdate,
        )

        data = StoreProductUpdate(
            name_en="Updated Product",
            price=75.0,
            sizes=[
                ProductSizeInput(size_label="L", size_system="general", stock=10, sort_order=0),
            ],
            pieces=[
                ProductPieceInput(name_en="Top", name_ar="Top", sort_order=0),
            ],
            color_sets=[
                ProductColorSetInput(
                    sort_order=0,
                    values=[ProductColorSetValueInput(piece_id="0", color_option_id="opt-red")],
                ),
            ],
            attribute_values=[],
            variants=[],
            images=[],
        )

        from app.services.product_definition_service import update_store_product

        mock_db = AsyncMock(spec=AsyncSession)

        async def _execute(stmt, *args, **kwargs):
            sql = str(stmt)
            result = MagicMock()
            if "product_color_set_values" in sql or "product_color_sets" in sql or "product_pieces" in sql:
                result.scalars.return_value.all.return_value = []
            elif "attribute_options" in sql:
                result.all.return_value = [("opt-red",)]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db.execute.side_effect = _execute

        result = await update_store_product(mock_db, "product-1", "store-1", data)
        assert result.name_en == "Updated Product"
        mock_repo.get.assert_called_once_with("product-1")


@pytest.mark.asyncio
async def test_update_store_product_rejects_unknown_piece_ref():
    with (
        patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls,
        patch("app.services.product_definition_service._resolve_attribute_values"),
        patch("app.services.product_definition_service._merge_variants"),
        patch("app.services.product_definition_service._update_product_images"),
    ):
        product = MagicMock()
        product.id = "product-1"
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        from app.schemas.product_definition import (
            ProductColorSetInput,
            ProductColorSetValueInput,
            StoreProductUpdate,
        )

        data = StoreProductUpdate(
            pieces=[],
            color_sets=[
                ProductColorSetInput(
                    sort_order=0,
                    values=[ProductColorSetValueInput(piece_id="ghost-piece", color_option_id="opt-red")],
                ),
            ],
            variants=[],
        )

        from app.services.product_definition_service import update_store_product

        mock_db = AsyncMock(spec=AsyncSession)

        async def _execute(stmt, *args, **kwargs):
            sql = str(stmt)
            result = MagicMock()
            if "product_color_set_values" in sql or "product_color_sets" in sql or "product_pieces" in sql:
                result.scalars.return_value.all.return_value = []
            elif "attribute_options" in sql:
                result.all.return_value = [("opt-red",)]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db.execute.side_effect = _execute

        with pytest.raises(ValidationError, match="Invalid piece reference"):
            await update_store_product(mock_db, "product-1", "store-1", data)


@pytest.mark.asyncio
async def test_update_store_product_rejects_unknown_color_option():
    with (
        patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls,
        patch("app.services.product_definition_service._resolve_attribute_values"),
        patch("app.services.product_definition_service._merge_variants"),
        patch("app.services.product_definition_service._update_product_images"),
    ):
        product = MagicMock()
        product.id = "product-1"
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        from app.schemas.product_definition import (
            ProductColorSetInput,
            ProductColorSetValueInput,
            ProductPieceInput,
            StoreProductUpdate,
        )

        data = StoreProductUpdate(
            pieces=[ProductPieceInput(name_en="Top", name_ar="Top", sort_order=0)],
            color_sets=[
                ProductColorSetInput(
                    sort_order=0,
                    values=[ProductColorSetValueInput(piece_id="0", color_option_id="no-such-option")],
                ),
            ],
            variants=[],
        )

        from app.services.product_definition_service import update_store_product

        mock_db = AsyncMock(spec=AsyncSession)

        async def _execute(stmt, *args, **kwargs):
            sql = str(stmt)
            result = MagicMock()
            if "product_color_set_values" in sql or "product_color_sets" in sql or "product_pieces" in sql:
                result.scalars.return_value.all.return_value = []
            elif "attribute_options" in sql:
                result.all.return_value = [("opt-red",)]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db.execute.side_effect = _execute

        with pytest.raises(ValidationError, match="Invalid color option reference"):
            await update_store_product(mock_db, "product-1", "store-1", data)


@pytest.mark.asyncio
async def test_update_store_product_not_found():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "other-store"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        from app.schemas.product_definition import StoreProductUpdate

        data = StoreProductUpdate()
        from app.services.product_definition_service import update_store_product

        with pytest.raises(NotFoundError, match="Product not found"):
            await update_store_product(AsyncMock(), "product-1", "store-1", data)


@pytest.mark.asyncio
async def test_merge_variants_empty_deletes_all():
    with patch("app.services.product_definition_service.StoreProductRepository"):
        mock_db = AsyncMock(spec=AsyncSession)
        existing_v = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_v]
        mock_db.execute.return_value = mock_result

        from app.services.product_definition_service import _merge_variants

        result = await _merge_variants(mock_db, "product-1", [])
        assert result == []
        mock_db.delete.assert_called_once_with(existing_v)


@pytest.mark.asyncio
async def test_update_product_variant_success():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        variant = MagicMock()
        variant.is_active = True
        variant.price = 50.0
        variant.sku = "SKU-001"
        variant.id = "variant-1"

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = variant
        mock_result.scalars.return_value.all.return_value = []
        mock_result.unique.return_value.scalar_one.return_value = variant
        mock_db.execute.return_value = mock_result

        from app.schemas.product_definition import ProductVariantUpdate
        from app.services.product_definition_service import update_product_variant

        data = ProductVariantUpdate(price=65.0, quantity=20)
        result = await update_product_variant(mock_db, "product-1", "store-1", "variant-1", data)
        assert result.price == 65.0


@pytest.mark.asyncio
async def test_get_categories_tree_with_product_type_filter():
    with patch("app.services.product_definition_service.CategoryRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_by_product_type_dto.return_value = [
            {
                "id": "cat-1",
                "parent_id": None,
                "product_type_id": "pt-1",
                "name_ar": "Cat",
                "name_en": "Cat",
                "name_fa": "Cat",
                "icon": "folder",
                "sort_order": 1,
                "is_active": True,
            }
        ]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_categories_tree

        result = await get_categories_tree(AsyncMock(), product_type_id="pt-1")
        assert len(result) == 1
        assert result[0].id == "cat-1"
        mock_repo.list_by_product_type_dto.assert_called_once_with("pt-1")


@pytest.mark.asyncio
async def test_resolve_attribute_values_multi_piece_color_derivation():
    mock_db = AsyncMock(spec=AsyncSession)
    attr_result = MagicMock()
    attr_result.one_or_none.return_value = ("attr-primary", "multi-select")
    mock_db.execute.return_value = attr_result

    from app.schemas.product_definition import (
        ProductAttributeValueInput,
        ProductColorSetInput,
        ProductColorSetValueInput,
        StoreProductCreate,
    )

    data = StoreProductCreate(
        product_type_id="pt-1",
        status="active",
        name_en="Test",
        price=10.0,
        is_multi_piece=True,
        color_sets=[
            ProductColorSetInput(
                sort_order=0,
                values=[
                    ProductColorSetValueInput(piece_id="0", color_option_id="opt-red"),
                    ProductColorSetValueInput(piece_id="1", color_option_id="opt-blue"),
                ],
            ),
        ],
        attribute_values=[
            ProductAttributeValueInput(attribute_id="attr-other", value="some-value"),
        ],
        pieces=[],
        variants=[],
        images=[],
        sizes=[],
    )

    from app.services.product_definition_service import _resolve_attribute_values

    result = await _resolve_attribute_values(mock_db, data, "product-1")
    # Should have the explicit attr value + 1 merged color value (JSON array)
    assert len(result) == 2
    color_av = next(av for av in result if av.attribute_id == "attr-primary")
    import json

    color_ids = json.loads(color_av.value)
    assert "opt-red" in color_ids
    assert "opt-blue" in color_ids


@pytest.mark.asyncio
async def test_get_product_type_detail_not_found():
    with patch("app.services.product_definition_service.ProductTypeRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_with_attributes.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_product_type_detail

        with pytest.raises(NotFoundError, match="Product type not found"):
            await get_product_type_detail(AsyncMock(), "nonexistent")


@pytest.mark.asyncio
async def test_get_categories_tree_with_nested():
    with patch("app.services.product_definition_service.CategoryRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_all_dto.return_value = [
            {
                "id": "parent-1",
                "parent_id": None,
                "product_type_id": "pt-1",
                "name_ar": "الوالد",
                "name_en": "Parent",
                "name_fa": "والد",
                "icon": "folder",
                "sort_order": 1,
                "is_active": True,
            },
            {
                "id": "child-1",
                "parent_id": "parent-1",
                "product_type_id": "pt-1",
                "name_ar": "الطفل",
                "name_en": "Child",
                "name_fa": "طفل",
                "icon": "subfolder",
                "sort_order": 1,
                "is_active": True,
            },
        ]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_categories_tree

        result = await get_categories_tree(AsyncMock())
        assert len(result) == 1
        assert len(result[0].children) == 1


@pytest.mark.asyncio
async def test_get_product_type_attributes_by_group():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_by_group_dto.return_value = [{"id": "attr-1"}]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_product_type_attributes

        result = await get_product_type_attributes(AsyncMock(), "pt-1", group_id="grp-fit")
        assert len(result) == 1
        mock_repo.list_by_group_dto.assert_called_once_with("grp-fit")


@pytest.mark.asyncio
async def test_get_product_type_attributes_ordered():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls, patch("app.services.product_definition_service._get_ordered_groups") as mock_groups_fn:
        mock_repo = AsyncMock()
        mock_repo.list_by_product_type_dto.return_value = [
            {"id": "a1", "group_id": "grp-1"},
            {"id": "a2", "group_id": "grp-2"},
        ]
        mock_repo_cls.return_value = mock_repo

        mock_groups_fn.return_value = [{"id": "grp-1"}, {"id": "grp-2"}]

        from app.services.product_definition_service import get_product_type_attributes

        result = await get_product_type_attributes(AsyncMock(), "pt-1")
        assert len(result) == 2
        assert result[0]["id"] == "a1"
        assert result[1]["id"] == "a2"


@pytest.mark.asyncio
async def test_get_attribute_groups_ordering():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    from app.services.product_definition_service import get_attribute_groups

    result = await get_attribute_groups(mock_db)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_attribute_options_not_found():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_attribute_options

        with pytest.raises(NotFoundError, match="Attribute not found"):
            await get_attribute_options(AsyncMock(), "nonexistent")


@pytest.mark.asyncio
async def test_get_attribute_options_success():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls, patch("app.services.product_definition_service.AttributeOptionRepository") as mock_opt_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = MagicMock()
        mock_repo_cls.return_value = mock_repo

        mock_opt_repo = AsyncMock()
        mock_opt_repo.list_by_attribute_dto.return_value = [{"id": "o1"}, {"id": "o2"}]
        mock_opt_repo_cls.return_value = mock_opt_repo

        from app.services.product_definition_service import get_attribute_options

        result = await get_attribute_options(AsyncMock(), "attr-1")
        assert len(result) == 2
        mock_opt_repo.list_by_attribute_dto.assert_called_once_with("attr-1")


@pytest.mark.asyncio
async def test_get_image_view_types():
    with patch("app.services.product_definition_service.ImageViewTypeRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_by_product_type_dto.return_value = [{"id": "vt-1"}]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_image_view_types

        result = await get_image_view_types(AsyncMock(), "pt-1")
        assert len(result) == 1


@pytest.mark.asyncio
async def test_get_variant_defining_attributes():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls:
        vd_attr = MagicMock(spec=Attribute)
        vd_attr.is_variant_defining = True
        non_vd = MagicMock(spec=Attribute)
        non_vd.is_variant_defining = False
        mock_repo = AsyncMock()
        mock_repo.list_by_product_type.return_value = [vd_attr, non_vd]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_variant_defining_attributes

        result = await get_variant_defining_attributes(AsyncMock(), "pt-1")
        assert len(result) == 1
        assert result[0].is_variant_defining is True


@pytest.mark.asyncio
async def test_get_variant_defining_attributes_none():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls:
        non_vd = MagicMock(spec=Attribute)
        non_vd.is_variant_defining = False
        mock_repo = AsyncMock()
        mock_repo.list_by_product_type.return_value = [non_vd]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_variant_defining_attributes

        result = await get_variant_defining_attributes(AsyncMock(), "pt-1")
        assert result == []


@pytest.mark.asyncio
async def test_generate_variant_combinations_no_selections():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        vd = MagicMock(spec=Attribute)
        vd.is_variant_defining = True
        vd.id = "vd-1"
        mock_repo.list_by_product_type.return_value = [vd]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import generate_variant_combinations

        result = await generate_variant_combinations(AsyncMock(), "pt-1", {})
        assert result == []


@pytest.mark.asyncio
async def test_generate_variant_combinations_cartesian():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls:
        opt1 = MagicMock()
        opt1.id = "opt-1"
        opt1.value_en = "Red"
        opt2 = MagicMock()
        opt2.id = "opt-2"
        opt2.value_en = "Blue"

        attr = MagicMock(spec=Attribute)
        attr.id = "color"
        attr.is_variant_defining = True
        attr.options = [opt1, opt2]

        mock_repo = AsyncMock()
        mock_repo.list_by_product_type.return_value = [attr]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import generate_variant_combinations

        result = await generate_variant_combinations(AsyncMock(), "pt-1", {"color": ["opt-1", "opt-2"]})
        assert len(result) == 2


@pytest.mark.asyncio
async def test_get_brands():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    from app.services.product_definition_service import get_brands

    result = await get_brands(mock_db)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_store_product_not_found():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_with_all.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_store_product

        with pytest.raises(NotFoundError, match="Product not found"):
            await get_store_product(AsyncMock(), "store-1", "nonexistent")


@pytest.mark.asyncio
async def test_list_my_products_empty_ids():
    from app.services.product_definition_service import list_my_products

    result = await list_my_products(AsyncMock(), [])
    assert result == ([], 0)


@pytest.mark.asyncio
async def test_add_product_image_not_found():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import add_product_image

        with pytest.raises(NotFoundError, match="Product not found"):
            await add_product_image(AsyncMock(), "product-1", "store-1", "http://example.com/img.jpg", view_type_id="vt-1")


@pytest.mark.asyncio
async def test_update_product_variant_product_not_found():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.schemas.product_definition import ProductVariantUpdate
        from app.services.product_definition_service import update_product_variant

        data = ProductVariantUpdate()
        with pytest.raises(NotFoundError, match="Product not found"):
            await update_product_variant(AsyncMock(), "product-1", "store-1", "variant-1", data)


@pytest.mark.asyncio
async def test_update_product_variant_not_found():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from app.schemas.product_definition import ProductVariantUpdate
        from app.services.product_definition_service import update_product_variant

        data = ProductVariantUpdate()
        with pytest.raises(NotFoundError, match="Variant not found"):
            await update_product_variant(mock_db, "product-1", "store-1", "nonexistent", data)


@pytest.mark.asyncio
async def test_update_product_variant_activate_without_price():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)
        variant = MagicMock()
        variant.is_active = False
        variant.price = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = variant
        mock_db.execute.return_value = mock_result

        from app.schemas.product_definition import ProductVariantUpdate
        from app.services.product_definition_service import update_product_variant

        data = ProductVariantUpdate(is_active=True, price=None)
        with pytest.raises(ValidationError, match="Price is required for active variants"):
            await update_product_variant(mock_db, "product-1", "store-1", "variant-1", data)


@pytest.mark.asyncio
async def test_update_product_variant_replace_options():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)
        variant = MagicMock()
        variant.is_active = True
        variant.price = 50.0
        variant.attribute_options = []
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = variant
        mock_result.scalars.return_value.all.return_value = []
        mock_result.unique.return_value.scalar_one.return_value = variant
        mock_db.execute.return_value = mock_result

        from app.schemas.product_definition import ProductVariantUpdate
        from app.services.product_definition_service import update_product_variant

        data = ProductVariantUpdate(attribute_option_ids=["opt-new"])
        result = await update_product_variant(mock_db, "product-1", "store-1", "variant-1", data)
        assert result is variant


@pytest.mark.asyncio
async def test_delete_product_variant_product_not_found():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import delete_product_variant

        with pytest.raises(NotFoundError, match="Product not found"):
            await delete_product_variant(AsyncMock(), "product-1", "store-1", "variant-1")


@pytest.mark.asyncio
async def test_delete_product_variant_not_found():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from app.services.product_definition_service import delete_product_variant

        with pytest.raises(NotFoundError, match="Variant not found"):
            await delete_product_variant(mock_db, "product-1", "store-1", "nonexistent")


@pytest.mark.asyncio
async def test_delete_product_variant_success():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)
        variant = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = variant
        mock_db.execute.return_value = mock_result

        from app.services.product_definition_service import delete_product_variant

        await delete_product_variant(mock_db, "product-1", "store-1", "variant-1")
        mock_db.delete.assert_called_once_with(variant)
        mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_variant_create_sku_required():
    from app.schemas.product_definition import ProductVariantCreate

    with pytest.raises(ValueError, match="SKU is required for active variants"):
        ProductVariantCreate(sku="", price=10.0, is_active=True, attribute_option_ids=["opt-1"])

    with pytest.raises(ValueError, match="SKU is required for active variants"):
        ProductVariantCreate(sku="   ", price=10.0, is_active=True, attribute_option_ids=["opt-1"])


@pytest.mark.asyncio
async def test_variant_create_sku_not_required_when_inactive():
    from app.schemas.product_definition import ProductVariantCreate

    variant = ProductVariantCreate(sku="", price=None, is_active=False, attribute_option_ids=[])
    assert variant.sku == ""


@pytest.mark.asyncio
async def test_update_variant_activate_without_sku():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        product = MagicMock()
        product.store_id = "store-1"
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)
        variant = MagicMock()
        variant.is_active = False
        variant.price = 10.0
        variant.sku = ""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = variant
        mock_db.execute.return_value = mock_result

        from app.schemas.product_definition import ProductVariantUpdate
        from app.services.product_definition_service import update_product_variant

        data = ProductVariantUpdate(is_active=True)
        with pytest.raises(ValidationError, match="SKU is required for active variants"):
            await update_product_variant(mock_db, "product-1", "store-1", "variant-1", data)


@pytest.mark.asyncio
async def test_get_product_types():
    with patch("app.services.product_definition_service.ProductTypeRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_all_dto.return_value = [{"id": "pt-1"}, {"id": "pt-2"}]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import get_product_types

        result = await get_product_types(AsyncMock())
        assert len(result) == 2


@pytest.mark.asyncio
async def test_variant_signature():
    from app.services.product_definition_service import _variant_signature

    assert _variant_signature(["c", "a", "b"]) == "a,b,c"
    assert _variant_signature([]) == ""
    assert _variant_signature(["x"]) == "x"


@pytest.mark.asyncio
async def test_deduplicate_variant_data():
    from app.schemas.product_definition import ProductVariantCreate
    from app.services.product_definition_service import _deduplicate_variant_data

    v1 = ProductVariantCreate(sku="V1", price=10.0, quantity=1, is_active=True, attribute_option_ids=["a", "b"])
    v2 = ProductVariantCreate(sku="V2", price=10.0, quantity=1, is_active=True, attribute_option_ids=["b", "a"])
    v3 = ProductVariantCreate(sku="V3", price=10.0, quantity=1, is_active=True, attribute_option_ids=["c"])

    result = _deduplicate_variant_data([v1, v2, v3])
    assert len(result) == 2
    assert result[0].sku == "V1"
    assert result[1].sku == "V3"


@pytest.mark.asyncio
async def test_create_variant_with_options():
    mock_db = AsyncMock(spec=AsyncSession)

    from app.schemas.product_definition import ProductVariantCreate
    from app.services.product_definition_service import _create_variant

    data = ProductVariantCreate(sku="NEW-V", price=25.0, quantity=5, is_active=True, attribute_option_ids=["opt-1", "opt-2"], color_set_id=None)
    variant = await _create_variant(mock_db, "product-1", data)
    assert variant.sku == "NEW-V"
    assert variant.product_id == "product-1"
    # Should have added 2 VariantAttributeOption links
    assert mock_db.add.call_count == 3  # variant + 2 links


@pytest.mark.asyncio
async def test_build_existing_variant_map():
    mock_db = AsyncMock(spec=AsyncSession)

    v1 = MagicMock()
    v1.id = "v-1"
    v1.attribute_options = []
    variant_result = MagicMock()
    variant_result.scalars.return_value.all.return_value = [v1]
    options_result = MagicMock()
    options_result.scalars.return_value.all.return_value = ["opt-a", "opt-b"]
    mock_db.execute.side_effect = [variant_result, options_result]

    from app.services.product_definition_service import _build_existing_variant_map

    result = await _build_existing_variant_map(mock_db, "product-1")
    assert "opt-a,opt-b" in result
    assert result["opt-a,opt-b"].id == "v-1"


@pytest.mark.asyncio
async def test_get_attribute_options_through_repo():
    with patch("app.services.product_definition_service.AttributeRepository") as mock_repo_cls, patch("app.services.product_definition_service.AttributeOptionRepository") as mock_opt_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = MagicMock()
        mock_repo_cls.return_value = mock_repo

        mock_opt_repo = AsyncMock()
        mock_opt_repo.list_by_attribute_dto.return_value = [{"id": "o1"}, {"id": "o2"}]
        mock_opt_repo_cls.return_value = mock_opt_repo

        from app.services.product_definition_service import get_attribute_options

        result = await get_attribute_options(AsyncMock(), "attr-1")
        assert len(result) == 2
