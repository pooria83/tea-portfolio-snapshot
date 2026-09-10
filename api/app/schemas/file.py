from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    file_name: str = Field(..., examples=["uuid-extracted-from-image.jpg"])
    original_name: str = Field(..., examples=["product-image.jpg"])
    content_type: str = Field(..., examples=["image/jpeg"])
    size: int = Field(..., ge=0, examples=[1048576])
    url: str = Field(..., examples=["http://localhost:9000/product-graph/uuid.jpg?X-Amz-Algorithm=..."])


class FileResponse(BaseModel):
    file_name: str
    original_name: str
    content_type: str
    size: int
    url: str
