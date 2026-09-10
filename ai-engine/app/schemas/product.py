from pydantic import BaseModel


class Attribute(BaseModel):
    name: str
    value: str


class ProductData(BaseModel):
    name_en: str | None = None
    name_ar: str | None = None
    name_fa: str | None = None
    brand: str | None = None
    category_name: str | None = None
    image_alt_texts: list[str] = []
    attributes: list[Attribute] = []
    price: float | None = None
    currency: str = "SAR"


class GenerateDescriptionRequest(BaseModel):
    product: ProductData
    prompt: str | None = None
    model: str | None = None


class DescriptionResponse(BaseModel):
    descriptions: dict[str, str]
    model: str
    tokens_used: int
    prompt: str
