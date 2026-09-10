from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.cache import CacheKeys, cache_or_fetch
from app.models.llm import LLMApiKey, LLMModel
from app.models.llm_setting import LLMSetting
from app.repositories.base import BaseRepository


class LLMModelRepository(BaseRepository[LLMModel]):
    model = LLMModel
    TOUCHES: frozenset[str] = frozenset({"llm_models", "llm_api_keys"})

    async def list_with_api_keys(self) -> list[LLMModel]:
        stmt = select(LLMModel).options(selectinload(LLMModel.api_keys)).order_by(LLMModel.provider, LLMModel.model)
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_active_with_api_keys(self, model_id: str) -> LLMModel | None:
        stmt = (
            select(LLMModel).options(selectinload(LLMModel.api_keys)).where(LLMModel.id == model_id, LLMModel.is_active == True)  # noqa: E712
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def exists_by_provider_model(self, provider: str, model_name: str) -> bool:
        result = await self.db.execute(select(LLMModel).where(LLMModel.provider == provider, LLMModel.model == model_name))
        return result.scalar_one_or_none() is not None


class LLMApiKeyRepository(BaseRepository[LLMApiKey]):
    model = LLMApiKey
    TOUCHES: frozenset[str] = frozenset({"llm_api_keys"})


class LLMSettingRepository(BaseRepository[LLMSetting]):
    model = LLMSetting
    TOUCHES: frozenset[str] = frozenset({"llm_settings"})

    async def get_single(self) -> LLMSetting | None:
        result = await self.db.execute(select(LLMSetting).limit(1))
        return result.scalar_one_or_none()

    async def get_single_dto(self) -> dict[str, str | None] | None:
        """Cached DTO read (model ids only). Writes must use :meth:`get_single`."""

        async def _fetch() -> dict[str, str | None] | None:
            setting = await self.get_single()
            if setting is None:
                return None
            return {
                "default_llm_model_id": setting.default_llm_model_id,
                "user_comm_model_id": setting.user_comm_model_id,
            }

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, CacheKeys.LLM_SETTING.prefix, CacheKeys.LLM_SETTING.ttl, _fetch, lock=True)
