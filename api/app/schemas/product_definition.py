from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductTypeResponse(BaseModel):
    id: str
    code: str
    name_ar: str
    name_en: str
    name_fa: str
    icon: str | None = None
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class AttributeGroupResponse(BaseModel):
    id: str
    code: str
    name_ar: str
    name_en: str
    name_fa: str
    icon: str | None = None
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class AttributeOptionResponse(BaseModel):
    id: str
    code: str | None = None
    value_ar: str
    value_en: str
    value_fa: str
    icon: str | None = None
    color_hex: str | None = None
    image_url: str | None = None
    color_family: str | None = None
    is_major: bool = False
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class AttributeResponse(BaseModel):
    id: str
    group_id: str
    group_code: str = ""
    code: str
    name_ar: str
    name_en: str
    name_fa: str
    description_ar: str | None = None
    description_en: str | None = None
    description_fa: str | None = None
    value_type: str
    input_type: str
    icon: str | None = None
    unit: str | None = None
    is_required: bool = False
    validation_rules: list[dict[str, object]] | None = None
    is_filterable: bool = True
    is_searchable: bool = True
    is_search_affecting: bool = False
    is_visible_on_show: bool = True
    is_variant_defining: bool = False
    sort_order: int = 0
    options: list[AttributeOptionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductTypeDetailResponse(ProductTypeResponse):
    categories: list["CategoryTreeResponse"] = []
    attributes: list[AttributeResponse] = []


class CategoryTreeResponse(BaseModel):
    id: str
    parent_id: str | None = None
    product_type_id: str | None = None
    name_ar: str
    name_en: str
    name_fa: str
    icon: str | None = None
    sort_order: int = 0
    is_active: bool = True
    children: list["CategoryTreeResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class ImageViewTypeResponse(BaseModel):
    id: str
    product_type_id: str
    code: str
    name_ar: str
    name_en: str
    name_fa: str
    is_video: bool = False
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class ProductImageInput(BaseModel):
    image_url: str
    view_type_id: str | None = None
    variant_index: int | None = None
    variant_signature: list[str] | None = None
    alt_text_ar: str | None = None
    alt_text_en: str | None = None
    alt_text_fa: str | None = None
    sort_order: int = 0


class ProductImageCreate(BaseModel):
    image_url: str
    view_type_id: str | None = None
    variant_id: str | None = None
    alt_text_ar: str | None = None
    alt_text_en: str | None = None
    alt_text_fa: str | None = None


class ProductImageResponse(BaseModel):
    id: str
    product_id: str
    variant_id: str | None = None
    view_type_id: str | None = None
    image_url: str
    alt_text_ar: str | None = None
    alt_text_en: str | None = None
    alt_text_fa: str | None = None
    sort_order: int = 0
    is_video: bool = False

    model_config = ConfigDict(from_attributes=True)


class ProductSizeInput(BaseModel):
    size_label: str = Field(..., max_length=50)
    size_system: str = Field(..., max_length=20)
    stock: int = 0
    sort_order: int = 0


class ProductSizeResponse(BaseModel):
    id: str
    product_id: str
    size_label: str
    size_system: str
    stock: int = 0
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class ProductPieceInput(BaseModel):
    name_en: str | None = None
    name_ar: str | None = None
    sort_order: int = 0


class ProductPieceResponse(BaseModel):
    id: str
    name_en: str | None = None
    name_ar: str | None = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class ProductColorSetValueInput(BaseModel):
    piece_id: str
    color_option_id: str


class ProductColorSetInput(BaseModel):
    sort_order: int = 0
    values: list[ProductColorSetValueInput] = []


class ProductColorSetValueResponse(BaseModel):
    id: str
    color_set_id: str
    piece_id: str
    piece_name_en: str | None = None
    piece_name_ar: str | None = None
    color_option_id: str
    color_option: AttributeOptionResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductColorSetResponse(BaseModel):
    id: str
    product_id: str
    sort_order: int
    values: list[ProductColorSetValueResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductAttributeValueInput(BaseModel):
    attribute_id: str
    value: str | None = None


class ProductAttributeValueResponse(BaseModel):
    id: str
    attribute_id: str
    value: str | None = None
    attribute: AttributeResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductVariantCreate(BaseModel):
    sku: str = Field(..., max_length=100)
    barcode: str | None = None
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    quantity: int = 0
    low_stock_threshold: int = 5
    weight: float | None = None
    is_active: bool = True
    color_set_id: str | None = None
    attribute_option_ids: list[str] = []

    @model_validator(mode="after")
    def validate_active_variant(self) -> "ProductVariantCreate":
        if self.is_active:
            if not self.sku or not self.sku.strip():
                raise ValueError("SKU is required for active variants")
            if self.price is None:
                raise ValueError("Price is required for active variants")
        return self


class ProductVariantUpdate(BaseModel):
    sku: str | None = Field(None, max_length=100)
    barcode: str | None = None
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    quantity: int | None = None
    low_stock_threshold: int | None = None
    weight: float | None = None
    is_active: bool | None = None
    attribute_option_ids: list[str] | None = None


class ProductVariantResponse(BaseModel):
    id: str
    product_id: str
    sku: str
    barcode: str | None = None
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    quantity: int = 0
    low_stock_threshold: int = 5
    weight: float | None = None
    is_active: bool = True
    sort_order: int = 0
    color_set_id: str | None = None
    color_set: ProductColorSetResponse | None = None
    attribute_options: list[AttributeOptionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class StoreProductCreate(BaseModel):
    product_type_id: str
    category_id: str | None = None
    name_ar: str | None = None
    name_en: str | None = None
    name_fa: str | None = None
    short_description_ar: str | None = None
    short_description_en: str | None = None
    short_description_fa: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    long_description_fa: str | None = None
    brand: str | None = None
    sku: str | None = None
    barcode: str | None = None
    status: str = "draft"
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    currency: str = "SAR"
    quantity: int = 0
    low_stock_threshold: int = 5
    weight: float | None = None
    weight_unit: str = "kg"
    collection: str | None = None
    collection_ar: str | None = None
    country_of_origin: str | None = None
    model_height: str | None = None
    model_wears_size: str | None = None
    video_url: str | None = None
    source_url: str | None = None
    sizes: list[ProductSizeInput] = []
    attribute_values: list[ProductAttributeValueInput] = []
    variants: list[ProductVariantCreate] = []
    images: list[ProductImageInput] = []
    is_multi_piece: bool = False
    pieces: list[ProductPieceInput] = []
    color_sets: list[ProductColorSetInput] = []


class StoreProductUpdate(BaseModel):
    category_id: str | None = Field(None, max_length=36)
    name_ar: str | None = None
    name_en: str | None = None
    name_fa: str | None = None
    short_description_ar: str | None = None
    short_description_en: str | None = None
    short_description_fa: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    long_description_fa: str | None = None
    brand: str | None = None
    sku: str | None = None
    barcode: str | None = None
    status: str | None = None
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    currency: str | None = None
    quantity: int | None = None
    low_stock_threshold: int | None = None
    weight: float | None = None
    weight_unit: str | None = None
    collection: str | None = None
    collection_ar: str | None = None
    country_of_origin: str | None = None
    model_height: str | None = None
    model_wears_size: str | None = None
    video_url: str | None = None
    source_url: str | None = None
    sizes: list[ProductSizeInput] | None = None
    attribute_values: list[ProductAttributeValueInput] | None = None
    variants: list[ProductVariantCreate] | None = None
    images: list[ProductImageInput] | None = None
    is_multi_piece: bool | None = None
    pieces: list[ProductPieceInput] | None = None
    color_sets: list[ProductColorSetInput] | None = None
    ai_description_en: str | None = None
    ai_description_ar: str | None = None


class AIDescriptionVersionResponse(BaseModel):
    id: str
    description_en: str | None = None
    description_ar: str | None = None
    model: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StoreProductResponse(BaseModel):
    id: str
    store_id: str
    store_name: str | None = None
    product_type_id: str
    category_id: str | None = None
    name_ar: str | None = None
    name_en: str | None = None
    name_fa: str | None = None
    short_description_ar: str | None = None
    short_description_en: str | None = None
    short_description_fa: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    long_description_fa: str | None = None
    brand: str | None = None
    brand_name: str | None = None
    slug: str | None = None
    sku: str | None = None
    barcode: str | None = None
    status: str = "draft"
    has_variants: bool = False
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    currency: str = "SAR"
    quantity: int = 0
    low_stock_threshold: int = 5
    weight: float | None = None
    weight_unit: str = "kg"
    collection: str | None = None
    collection_ar: str | None = None
    country_of_origin: str | None = None
    care_instructions_ar: str | None = None
    care_instructions_en: str | None = None
    care_instructions_fa: str | None = None
    model_height: str | None = None
    model_wears_size: str | None = None
    video_url: str | None = None
    source_url: str | None = None
    meta_title_ar: str | None = None
    meta_title_en: str | None = None
    meta_title_fa: str | None = None
    meta_description_ar: str | None = None
    meta_description_en: str | None = None
    meta_description_fa: str | None = None
    embedding_text: str | None = None
    created_at: datetime
    updated_at: datetime
    images: list[ProductImageResponse] = []
    sizes: list[ProductSizeResponse] = []
    attribute_values: list[ProductAttributeValueResponse] = []
    variants: list[ProductVariantResponse] = []
    is_multi_piece: bool = False
    pieces: list[ProductPieceResponse] = []
    color_sets: list[ProductColorSetResponse] = []

    ai_description_en: str | None = None
    ai_description_ar: str | None = None
    ai_description_versions: list[AIDescriptionVersionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class StoreProductListItem(BaseModel):
    """Lightweight product list card — no variants/images/descriptions payloads."""

    id: str
    store_id: str
    store_name: str | None = None
    product_type_id: str
    name_ar: str | None = None
    name_en: str | None = None
    name_fa: str | None = None
    brand_name: str | None = None
    status: str = "draft"
    has_variants: bool = False
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    currency: str = "SAR"
    quantity: int = 0
    image_url: str | None = None


class GenerateDescriptionsRequest(BaseModel):
    prompt: str | None = None
    model: str | None = None


class GenerateDescriptionResponse(BaseModel):
    descriptions: dict[str, str]
    model: str
    prompt: str
    history: list[AIDescriptionVersionResponse]


class ProductImageUpdate(BaseModel):
    view_type_id: str | None = None
    variant_id: str | None = None
    alt_text_ar: str | None = None
    alt_text_en: str | None = None
    alt_text_fa: str | None = None
    sort_order: int | None = None


class ProductImageReorder(BaseModel):
    id: str
    sort_order: int


class BrandResponse(BaseModel):
    id: str
    code: str
    name_ar: str
    name_en: str
    name_fa: str
    logo_url: str | None = None
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)
