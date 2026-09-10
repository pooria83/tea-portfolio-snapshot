from pydantic import BaseModel


class PromptTemplateUpdate(BaseModel):
    pre_prompt: str | None = None
    ending_prompt: str | None = None
    chat_assistant: str | None = None
    parse_query: str | None = None
    summarize: str | None = None
    title: str | None = None


class PromptTemplateResponse(BaseModel):
    pre_prompt: str
    ending_prompt: str
    chat_assistant: str
    parse_query: str
    summarize: str
    title: str
