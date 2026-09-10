from typing import Any

from sqlalchemy import select

from app.core.cache import CacheKeys, cache_or_fetch
from app.models.country import Country
from app.models.currency import Currency
from app.models.store_type import StoreType
from app.repositories.base import BaseRepository


class StoreTypeRepository(BaseRepository[StoreType]):
    model = StoreType
    TOUCHES: frozenset[str] = frozenset({"store_types"})

    async def list_active_dto(self, locale: str) -> list[dict[str, str]]:
        """Cached JSON-safe active store types localized to *locale*."""

        name_map = {"ar": "name_ar", "en": "name_en", "fa": "name_fa"}

        async def _fetch() -> list[dict[str, str]]:
            stmt = select(StoreType).where(StoreType.is_active == True).order_by(StoreType.name_en)  # noqa: E712
            result = await self.db.execute(stmt)
            return [{"id": st.id, "name": str(getattr(st, name_map.get(locale, "name_en")))} for st in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_STORE_TYPES.prefix}{locale}", CacheKeys.CAT_STORE_TYPES.ttl, _fetch)


class CountryRepository(BaseRepository[Country]):
    model = Country
    TOUCHES: frozenset[str] = frozenset({"countries"})

    async def list_dto(self) -> list[dict[str, Any]]:
        """Cached JSON-safe country rows."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(Country).order_by(Country.name_en)
            result = await self.db.execute(stmt)
            return [{"code": c.code, "name_ar": c.name_ar, "name_en": c.name_en, "name_fa": c.name_fa} for c in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_COUNTRIES.prefix}all", CacheKeys.CAT_COUNTRIES.ttl, _fetch)


class CurrencyRepository(BaseRepository[Currency]):
    model = Currency
    TOUCHES: frozenset[str] = frozenset({"currencies"})

    async def list_dto(self) -> list[dict[str, Any]]:
        """Cached JSON-safe currency rows."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(Currency).order_by(Currency.code)
            result = await self.db.execute(stmt)
            return [{"code": c.code, "name_ar": c.name_ar, "name_en": c.name_en, "name_fa": c.name_fa, "symbol": c.symbol} for c in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_CURRENCIES.prefix}all", CacheKeys.CAT_CURRENCIES.ttl, _fetch)
