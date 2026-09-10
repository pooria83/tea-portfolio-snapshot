from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LLMApiKeyResponse(BaseModel):
    id: str
    model_id: str
    name: str | None = None
    is_active: bool
    masked_key: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LLMModelResponse(BaseModel):
    id: str
    provider: str
    model: str
    is_active: bool
    context_window: int | None = None
    api_keys: list[LLMApiKeyResponse]

    model_config = ConfigDict(from_attributes=True)


class AddApiKeyRequest(BaseModel):
    model_id: str
    name: str | None = None
    api_key: str


class AddApiKeyResponse(BaseModel):
    id: str
    model_id: str
    name: str | None = None
    is_active: bool
    masked_key: str
    created_at: datetime


class LLMSettingsResponse(BaseModel):
    default_llm_model_id: str | None = None
    default_llm_model: LLMModelResponse | None = None
    user_comm_model_id: str | None = None
    user_comm_model: LLMModelResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class LLMSettingsUpdate(BaseModel):
    default_llm_model_id: str | None = None
    user_comm_model_id: str | None = None
