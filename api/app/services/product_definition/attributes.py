"""Attribute value resolution for store products."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attribute import Attribute
from app.models.product_attribute_value import ProductAttributeValue
from app.schemas.product_definition import StoreProductCreate, StoreProductUpdate

PRIMARY_COLOR_ATTR_CODE = "primary_color"


async def _resolve_attribute_values(
    db: AsyncSession,
    data: StoreProductCreate | StoreProductUpdate,
    product_id: str,
) -> list[ProductAttributeValue]:
    """Merge explicit attribute_values with auto-derived colors from color sets."""
    attr_values: list[ProductAttributeValue] = []

    for av_data in data.attribute_values or []:
        attr_values.append(
            ProductAttributeValue(
                id=str(uuid.uuid4()),
                product_id=product_id,
                attribute_id=av_data.attribute_id,
                value=av_data.value,
            )
        )

    is_multi = data.is_multi_piece if hasattr(data, "is_multi_piece") else False
    color_sets = data.color_sets if hasattr(data, "color_sets") else []
    if is_multi and color_sets:
        color_ids: set[str] = set()
        for cs in color_sets:
            for val in cs.values:
                if val.color_option_id:
                    color_ids.add(val.color_option_id)

        if color_ids:
            result = await db.execute(select(Attribute.id, Attribute.input_type).where(Attribute.code == PRIMARY_COLOR_ATTR_CODE))
            row = result.one_or_none()
            if row:
                primary_attr_id, input_type = row
                if input_type == "multi-select":
                    existing_ids: set[str] = set()
                    for av in list(attr_values):
                        if av.attribute_id == primary_attr_id and av.value:
                            try:
                                parsed = json.loads(av.value)
                                if isinstance(parsed, list):
                                    existing_ids.update(str(x) for x in parsed)
                                else:
                                    existing_ids.add(av.value)
                            except (json.JSONDecodeError, TypeError):
                                existing_ids.add(av.value)
                    all_ids = existing_ids | color_ids
                    if all_ids:
                        attr_values = [av for av in attr_values if av.attribute_id != primary_attr_id]
                        attr_values.append(
                            ProductAttributeValue(
                                id=str(uuid.uuid4()),
                                product_id=product_id,
                                attribute_id=primary_attr_id,
                                value=json.dumps(list(all_ids)),
                            )
                        )
                else:
                    existing = {av.value for av in attr_values if av.attribute_id == primary_attr_id}
                    for cid in color_ids:
                        if cid not in existing:
                            attr_values.append(
                                ProductAttributeValue(
                                    id=str(uuid.uuid4()),
                                    product_id=product_id,
                                    attribute_id=primary_attr_id,
                                    value=cid,
                                )
                            )

    return attr_values
