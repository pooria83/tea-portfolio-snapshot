export interface AttributeOptionItem {
  id: string;
  code: string | null;
  value_ar: string;
  value_en: string;
  value_fa: string;
  icon: string | null;
  color_hex: string | null;
  image_url: string | null;
  color_family: string | null;
  is_major: boolean;
  sort_order: number;
}

export interface AttributeItem {
  id: string;
  group_id: string;
  code: string;
  name_ar: string;
  name_en: string;
  name_fa: string;
  description_ar: string | null;
  description_en: string | null;
  description_fa: string | null;
  value_type: string;
  input_type: string;
  icon: string | null;
  unit: string | null;
  is_required: boolean;
  is_filterable: boolean;
  is_searchable: boolean;
  is_visible_on_show: boolean;
  is_variant_defining: boolean;
  sort_order: number;
  options: AttributeOptionItem[];
  validation_rules: unknown[] | null;
}

export interface ProductImageItem {
  id: string;
  product_id: string;
  variant_id: string | null;
  view_type_id: string | null;
  image_url: string;
  alt_text_ar: string | null;
  alt_text_en: string | null;
  alt_text_fa: string | null;
  sort_order: number;
  is_video: boolean;
}

export interface ProductPieceResponse {
  id: string;
  name_en: string | null;
  name_ar: string | null;
  sort_order: number;
}

export interface ProductColorSetValueResponse {
  id: string;
  color_set_id: string;
  piece_id: string;
  piece_name_en: string | null;
  piece_name_ar: string | null;
  color_option_id: string;
  color_option: AttributeOptionItem | null;
}

export interface ProductColorSetResponse {
  id: string;
  product_id: string;
  sort_order: number;
  values: ProductColorSetValueResponse[];
}

export interface ProductVariantResponse {
  id: string;
  product_id: string;
  sku: string;
  barcode: string | null;
  price: number | null;
  original_price: number | null;
  sale_price: number | null;
  quantity: number;
  low_stock_threshold: number;
  weight: number | null;
  is_active: boolean;
  sort_order: number;
  color_set_id: string | null;
  color_set: ProductColorSetResponse | null;
  attribute_options: AttributeOptionItem[];
}

export interface ProductResponse {
  id: string;
  store_id: string;
  store_name?: string | null;
  product_type_id: string;
  category_id: string | null;
  name_ar: string | null;
  name_en: string | null;
  name_fa: string | null;
  short_description_ar: string | null;
  short_description_en: string | null;
  short_description_fa: string | null;
  long_description_ar: string | null;
  long_description_en: string | null;
  long_description_fa: string | null;
  brand: string | null;
  brand_name: string | null;
  status: string;
  has_variants: boolean;
  price: number | null;
  original_price: number | null;
  sale_price: number | null;
  currency: string;
  quantity: number;
  collection: string | null;
  collection_ar: string | null;
  source_url?: string | null;
  ai_description_en: string | null;
  ai_description_ar: string | null;
  ai_description_versions: {
    id: string;
    description_en: string | null;
    description_ar: string | null;
    model: string | null;
    created_at: string;
  }[];
  images: ProductImageItem[];
  sizes: {
    id: string;
    size_label: string;
    size_system: string;
    stock: number;
    sort_order: number;
  }[];
  attribute_values: {id: string; attribute_id: string; value: string | null}[];
  variants: ProductVariantResponse[];
  is_multi_piece: boolean;
  pieces: ProductPieceResponse[];
  color_sets: ProductColorSetResponse[];
  created_at: string;
  updated_at: string;
}
