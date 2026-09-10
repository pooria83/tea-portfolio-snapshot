from pydantic import BaseModel, Field


class EmbedTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000, examples=["silk summer dress with floral pattern"])


class EmbedTextResponse(BaseModel):
    model: str
    dimensions: int
    embedding: list[float]
