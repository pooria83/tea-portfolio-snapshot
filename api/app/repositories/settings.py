from sqlalchemy import select, update

from app.core.cache import CacheKeys, cache_or_fetch
from app.models.prompt_template import PromptTemplate
from app.models.system_setting import SystemSetting
from app.repositories.base import BaseRepository


class SystemSettingRepository(BaseRepository[SystemSetting]):
    model = SystemSetting
    TOUCHES: frozenset[str] = frozenset({"system_settings"})

    @staticmethod
    def _dto(setting: SystemSetting) -> dict[str, str]:
        return {"key": setting.key, "value": setting.value}

    async def list_all(self) -> list[dict[str, str]]:
        async def _fetch() -> list[dict[str, str]]:
            stmt = select(SystemSetting).order_by(SystemSetting.key)
            result = await self.db.execute(stmt)
            return [self._dto(s) for s in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, CacheKeys.SYSTEM_SETTINGS.prefix + "all", CacheKeys.SYSTEM_SETTINGS.ttl, _fetch)

    async def get_by_key(self, key: str) -> dict[str, str] | None:
        """Cached DTO read. Write paths must use :meth:`get_by_key_orm`."""

        async def _fetch() -> dict[str, str] | None:
            setting = await self.get_by_key_orm(key)
            return self._dto(setting) if setting else None

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, CacheKeys.system_setting(key), CacheKeys.SYSTEM_SETTING.ttl, _fetch, lock=True)

    async def get_by_key_orm(self, key: str) -> SystemSetting | None:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_keys(self, keys: list[str]) -> list[dict[str, str]]:
        signature = ",".join(sorted(keys))

        async def _fetch() -> list[dict[str, str]]:
            stmt = select(SystemSetting).where(SystemSetting.key.in_(keys))
            result = await self.db.execute(stmt)
            return [self._dto(s) for s in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.SYSTEM_SETTINGS.prefix}bykeys:{signature}", CacheKeys.SYSTEM_SETTINGS.ttl, _fetch)


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    model = PromptTemplate
    TOUCHES: frozenset[str] = frozenset({"prompt_templates"})

    async def get_active_content(self, type_: str) -> str | None:
        async def _fetch() -> str | None:
            stmt = (
                select(PromptTemplate.content)
                .where(PromptTemplate.type == type_, PromptTemplate.is_active == True)  # noqa: E712
                .order_by(PromptTemplate.created_at.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, CacheKeys.prompt(type_), CacheKeys.PROMPT.ttl, _fetch)

    async def deactivate_active(self, type_: str) -> None:
        await self.db.execute(
            update(PromptTemplate)
            .where(PromptTemplate.type == type_, PromptTemplate.is_active == True)  # noqa: E712
            .values(is_active=False)
        )
        await self._invalidate()
