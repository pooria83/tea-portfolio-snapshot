from pydantic import BaseModel, ConfigDict


class StoreTypeResponse(BaseModel):
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)
