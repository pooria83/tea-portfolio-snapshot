from pydantic import BaseModel, ConfigDict


class EmbedModelResponse(BaseModel):
    id: str
    model_name: str
    display_name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
