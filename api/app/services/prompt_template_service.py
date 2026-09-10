import uuid

from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_tables
from app.models.prompt_template import PromptTemplate
from app.repositories.settings import PromptTemplateRepository
from app.schemas.prompt_template import PromptTemplateResponse, PromptTemplateUpdate
from app.services.prompt_defaults import (
    CHAT_ASSISTANT,
    DEFAULT_CHAT_ASSISTANT_PROMPT,
    DEFAULT_ENDING_PROMPT,
    DEFAULT_PARSE_QUERY_PROMPT,
    DEFAULT_PRE_PROMPT,
    DEFAULT_SUMMARIZE_PROMPT,
    DEFAULT_TITLE_PROMPT,
    ENDING_PROMPT,
    PARSE_QUERY,
    PRE_PROMPT,
    SUMMARIZE,
    TITLE,
)

PROMPT_FIELDS = (
    (PRE_PROMPT, DEFAULT_PRE_PROMPT),
    (ENDING_PROMPT, DEFAULT_ENDING_PROMPT),
    (CHAT_ASSISTANT, DEFAULT_CHAT_ASSISTANT_PROMPT),
    (PARSE_QUERY, DEFAULT_PARSE_QUERY_PROMPT),
    (SUMMARIZE, DEFAULT_SUMMARIZE_PROMPT),
    (TITLE, DEFAULT_TITLE_PROMPT),
)


async def get_active_content(db: AsyncSession, type_: str, default: str, redis: AsyncRedis | None = None) -> str:
    content = await PromptTemplateRepository(db, redis).get_active_content(type_)
    return content if content is not None else default


async def get_prompt_response(db: AsyncSession, redis: AsyncRedis | None = None) -> PromptTemplateResponse:
    kwargs: dict[str, str] = {}
    for type_, default in PROMPT_FIELDS:
        kwargs[type_] = await get_active_content(db, type_, default, redis)
    return PromptTemplateResponse(**kwargs)


async def update_templates(db: AsyncSession, body: PromptTemplateUpdate, redis: AsyncRedis | None = None) -> PromptTemplateResponse:
    repo = PromptTemplateRepository(db, redis)
    for type_, _default in PROMPT_FIELDS:
        content = getattr(body, type_)
        if content is not None:
            await repo.deactivate_active(type_)
            db.add(PromptTemplate(id=str(uuid.uuid4()), type=type_, content=content, is_active=True))
    await db.commit()
    if redis is not None:
        await invalidate_tables(redis, {"prompt_templates"})
    return await get_prompt_response(db, redis)
