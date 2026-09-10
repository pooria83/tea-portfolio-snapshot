from pydantic import BaseModel


class SystemSettingResponse(BaseModel):
    key: str
    value: str


class SystemSettingUpdate(BaseModel):
    key: str
    value: str
