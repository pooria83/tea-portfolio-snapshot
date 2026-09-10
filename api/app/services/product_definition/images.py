"""Product image update helpers."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.product_image import ProductImage
from app.models.product_variant import ProductVariant
from app.models.store_product import StoreProduct
from app.repositories.product_definition import StoreProductRepository
from app.schemas.product_definition import ProductImageInput


async def _update_product_images(db: AsyncSession, product_id: str, images: list[ProductImageInput], store_product: StoreProduct) -> None:
    repo = StoreProductRepository(db)
    await repo.delete_images(product_id)
    stmt = select(ProductVariant).options(joinedload(ProductVariant.attribute_options)).where(ProductVariant.product_id == product_id).order_by(ProductVariant.sort_order)
    result = await db.execute(stmt)
    current_variants = result.unique().scalars().all()
    for img_data in images:
        if img_data.variant_signature:
            sig_set = set(img_data.variant_signature)
            matched = False
            for v in current_variants:
                v_attr_ids = {o.id for o in v.attribute_options}
                if sig_set and sig_set.issubset(v_attr_ids):
                    image = ProductImage(
                        id=str(uuid.uuid4()),
                        product_id=store_product.id,
                        variant_id=v.id,
                        view_type_id=img_data.view_type_id,
                        image_url=img_data.image_url,
                        alt_text_ar=img_data.alt_text_ar,
                        alt_text_en=img_data.alt_text_en,
                        alt_text_fa=img_data.alt_text_fa,
                        sort_order=img_data.sort_order,
                    )
                    db.add(image)
                    matched = True
                    break
            if matched:
                continue
        elif img_data.variant_index is not None and img_data.variant_index < len(current_variants):
            image = ProductImage(
                id=str(uuid.uuid4()),
                product_id=store_product.id,
                variant_id=current_variants[img_data.variant_index].id,
                view_type_id=img_data.view_type_id,
                image_url=img_data.image_url,
                alt_text_ar=img_data.alt_text_ar,
                alt_text_en=img_data.alt_text_en,
                alt_text_fa=img_data.alt_text_fa,
                sort_order=img_data.sort_order,
            )
            db.add(image)
            continue
        image = ProductImage(
            id=str(uuid.uuid4()),
            product_id=store_product.id,
            variant_id=None,
            view_type_id=img_data.view_type_id,
            image_url=img_data.image_url,
            alt_text_ar=img_data.alt_text_ar,
            alt_text_en=img_data.alt_text_en,
            alt_text_fa=img_data.alt_text_fa,
            sort_order=img_data.sort_order,
        )
        db.add(image)
