export interface ProductTypeOption {
  id: string;
  code: string;
  name_ar: string;
  name_en: string;
  name_fa: string;
  icon: string | null;
  sort_order: number;
}

export interface AttributeGroupItem {
  id: string;
  code: string;
  name_ar: string;
  name_en: string;
  name_fa: string;
  icon: string | null;
  sort_order: number;
}

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

export interface ValidationRule {
  type: string;
  message: {
    en: string;
    ar: string;
    fa: string;
  };
  value?: number | string;
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
  is_search_affecting: boolean;
  is_visible_on_show: boolean;
  is_variant_defining: boolean;
  sort_order: number;
  options: AttributeOptionItem[];
  validation_rules: ValidationRule[] | null;
}

export interface CategoryNode {
  id: string;
  parent_id: string | null;
  product_type_id: string | null;
  name_ar: string;
  name_en: string;
  name_fa: string;
  icon: string | null;
  sort_order: number;
  is_active: boolean;
  children: CategoryNode[];
}

export interface ImageViewTypeItem {
  id: string;
  product_type_id: string;
  code: string;
  name_ar: string;
  name_en: string;
  name_fa: string;
  is_video: boolean;
  sort_order: number;
}

export interface BrandItem {
  id: string;
  code: string;
  name_ar: string;
  name_en: string;
  name_fa: string;
  logo_url: string | null;
  sort_order: number;
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

export interface ProductImageInput {
  image_url: string;
  view_type_id: string | null;
  variant_index?: number | null;
  variant_signature?: string[] | null;
  alt_text_ar: string | null;
  alt_text_en: string | null;
  alt_text_fa: string | null;
  sort_order: number;
}

export interface ProductSizeInput {
  size_label: string;
  size_system: string;
  stock: number;
  sort_order: number;
}

export interface ProductPieceInput {
  name_en?: string | null;
  name_ar?: string | null;
  sort_order?: number;
}

export interface ProductPieceResponse {
  id: string;
  name_en: string | null;
  name_ar: string | null;
  sort_order: number;
}

export interface ProductColorSetValueInput {
  piece_id: string;
  color_option_id: string;
}

export interface ProductColorSetInput {
  sort_order?: number;
  values: ProductColorSetValueInput[];
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

export interface ProductAttributeValueInput {
  attribute_id: string;
  value: string | null;
}

export interface ProductVariantInput {
  sku: string;
  barcode?: string | null;
  price?: number | null;
  original_price?: number | null;
  sale_price?: number | null;
  quantity: number;
  low_stock_threshold: number;
  weight?: number | null;
  is_active: boolean;
  color_set_id?: string | null;
  attribute_option_ids: string[];
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

export interface ProductCreate {
  product_type_id: string;
  category_id?: string | null;
  name_ar?: string | null;
  name_en?: string | null;
  name_fa?: string | null;
  short_description_ar?: string | null;
  short_description_en?: string | null;
  short_description_fa?: string | null;
  long_description_ar?: string | null;
  long_description_en?: string | null;
  long_description_fa?: string | null;
  brand?: string | null;
  sku?: string | null;
  barcode?: string | null;
  status?: string;
  price?: number | null;
  original_price?: number | null;
  sale_price?: number | null;
  currency?: string;
  quantity?: number;
  low_stock_threshold?: number;
  weight?: number | null;
  weight_unit?: string;
  collection?: string | null;
  collection_ar?: string | null;
  country_of_origin?: string | null;
  model_height?: string | null;
  model_wears_size?: string | null;
  video_url?: string | null;
  source_url?: string | null;
  sizes?: ProductSizeInput[];
  attribute_values?: ProductAttributeValueInput[];
  variants?: ProductVariantInput[];
  images?: ProductImageInput[];
  is_multi_piece?: boolean;
  pieces?: ProductPieceInput[];
  color_sets?: ProductColorSetInput[];
}

export interface ProductUpdate {
  category_id?: string | null;
  name_ar?: string | null;
  name_en?: string | null;
  name_fa?: string | null;
  short_description_ar?: string | null;
  short_description_en?: string | null;
  short_description_fa?: string | null;
  long_description_ar?: string | null;
  long_description_en?: string | null;
  long_description_fa?: string | null;
  brand?: string | null;
  sku?: string | null;
  barcode?: string | null;
  status?: string;
  price?: number | null;
  original_price?: number | null;
  sale_price?: number | null;
  currency?: string;
  quantity?: number;
  low_stock_threshold?: number;
  weight?: number | null;
  weight_unit?: string;
  collection?: string | null;
  collection_ar?: string | null;
  country_of_origin?: string | null;
  model_height?: string | null;
  model_wears_size?: string | null;
  video_url?: string | null;
  source_url?: string | null;
  sizes?: ProductSizeInput[];
  attribute_values?: ProductAttributeValueInput[];
  variants?: ProductVariantInput[];
  images?: ProductImageInput[];
  is_multi_piece?: boolean | null;
  pieces?: ProductPieceInput[] | null;
  color_sets?: ProductColorSetInput[] | null;
  ai_description_en?: string | null;
  ai_description_ar?: string | null;
}

export interface AIDescriptionVersion {
  id: string;
  description_en: string | null;
  description_ar: string | null;
  model: string | null;
  created_at: string;
}

export interface GenerateDescriptionResponse {
  descriptions: { en: string; ar: string };
  model: string;
  prompt: string;
  history: AIDescriptionVersion[];
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
  ai_description_versions: AIDescriptionVersion[];
  images: ProductImageItem[];
  sizes: {
    id: string;
    size_label: string;
    size_system: string;
    stock: number;
    sort_order: number;
  }[];
  attribute_values: { id: string; attribute_id: string; value: string | null }[];
  variants: ProductVariantResponse[];
  is_multi_piece: boolean;
  pieces: ProductPieceResponse[];
  color_sets: ProductColorSetResponse[];
  created_at: string;
  updated_at: string;
}

export interface ProductListItem {
  id: string;
  store_id: string;
  store_name?: string | null;
  product_type_id: string;
  name_ar: string | null;
  name_en: string | null;
  name_fa: string | null;
  brand_name: string | null;
  status: string;
  has_variants: boolean;
  price: number | null;
  original_price: number | null;
  sale_price: number | null;
  currency: string;
  quantity: number;
  image_url: string | null;
}

export interface ProductStatsResponse {
  total: number;
  active: number;
}
