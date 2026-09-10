from pydantic import BaseModel, ConfigDict


class CountryItem(BaseModel):
    code: str
    name_ar: str
    name_en: str
    name_fa: str

    model_config = ConfigDict(from_attributes=True)


class CurrencyItem(BaseModel):
    code: str
    name_ar: str
    name_en: str
    name_fa: str
    symbol: str

    model_config = ConfigDict(from_attributes=True)
