import type {
  AttributeItem,
  ProductCreate,
  ProductVariantInput,
  ProductPieceInput,
  ProductColorSetInput,
} from "@/types/api";

export interface ImagePayloadItem {
  image_url: string;
  view_type_id: string | null;
  variant_signature: string[] | null;
  alt_text_ar: string;
  alt_text_en: string;
  alt_text_fa: string;
  sort_order: number;
}

export function buildBasicPayload(data: Record<string, string>, productTypeId: string) {
  return {
    product_type_id: productTypeId,
    status: "active" as const,
    name_en: data.name_en || null,
    name_ar: data.name_ar || null,
    name_fa: data.name_fa || data.name_en || null,
    brand: data.brand || null,
    category_id: data.category_id || null,
    collection: data.collection || null,
    collection_ar: data.collection_ar || null,
    short_description_ar: data.short_description_ar || null,
    short_description_en: data.short_description_en || null,
    long_description_ar: data.long_description_ar || null,
    long_description_en: data.long_description_en || null,
    source_url: data.source_url || null,
    price: data.price ? Number(data.price) : null,
    original_price: data.original_price ? Number(data.original_price) : null,
    quantity: data.quantity ? Number(data.quantity) : 0,
  };
}

export function buildAttributeValues(data: Record<string, string>, attributes: AttributeItem[]) {
  const result: { attribute_id: string; value: string | null }[] = [];
  for (const attr of attributes) {
    const val = data[`attr_${attr.id}`];
    if (val && val.length > 0) {
      result.push({ attribute_id: attr.id, value: val });
    }
  }
  return result;
}

export function buildVariantPayload(variants: ProductVariantInput[], productPrice: number | null) {
  return variants.map((v) => {
    const price = v.is_active && v.price == null ? productPrice : (v.price ?? null);
    return { ...v, price };
  });
}

export function buildImagePayload(images: ImagePayloadItem[]) {
  return images.map((img) => ({
    image_url: img.image_url,
    view_type_id: img.view_type_id,
    variant_signature: img.variant_signature,
    alt_text_ar: img.alt_text_ar || null,
    alt_text_en: img.alt_text_en || null,
    alt_text_fa: img.alt_text_fa || null,
    sort_order: img.sort_order,
  }));
}

export function buildProductPayload(
  data: Record<string, string>,
  productTypeId: string,
  variants: ProductVariantInput[],
  images: ImagePayloadItem[],
  attributes: AttributeItem[],
  isMultiPiece?: boolean,
  pieces?: ProductPieceInput[],
  colorSets?: ProductColorSetInput[],
  colorSetIdxToId?: Record<string, string>,
): ProductCreate {
  const payload: ProductCreate = buildBasicPayload(data, productTypeId);

  const attributeValues = buildAttributeValues(data, attributes);
  if (attributeValues.length > 0) payload.attribute_values = attributeValues;

  if (variants.length > 0) {
    const mappedVariants = variants.map((v) => {
      const mapped: ProductVariantInput = { ...v };
      if (v.color_set_id && colorSetIdxToId) {
        mapped.color_set_id = colorSetIdxToId[v.color_set_id] ?? v.color_set_id;
      } else if (v.color_set_id) {
        mapped.color_set_id = v.color_set_id;
      } else {
        delete (mapped as unknown as Record<string, unknown>).color_set_id;
      }
      return mapped;
    });
    payload.variants = buildVariantPayload(mappedVariants, data.price ? Number(data.price) : null);
  }

  if (images.length > 0) {
    payload.images = buildImagePayload(images);
  }

  if (isMultiPiece) {
    payload.is_multi_piece = true;
    const activePieces = pieces?.filter((p) => p.name_en?.trim()) || [];
    if (activePieces.length > 0) {
      payload.pieces = activePieces.map((p, i) => ({
        name_en: p.name_en || null,
        name_ar: p.name_ar || null,
        sort_order: i,
      }));
    }
    if (colorSets && colorSets.length > 0) {
      payload.color_sets = colorSets.map((cs, i) => ({
        sort_order: i,
        values: cs.values
          .filter((v) => v.color_option_id && v.piece_id)
          .map((v) => ({
            piece_id: v.piece_id,
            color_option_id: v.color_option_id,
          })),
      }));
    }
  }

  return payload;
}
