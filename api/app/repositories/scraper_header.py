from sqlalchemy import select

from app.models.scraper_header import ScraperHeader
from app.repositories.base import BaseRepository


class ScraperHeaderRepository(BaseRepository[ScraperHeader]):
    model = ScraperHeader
    TOUCHES: frozenset[str] = frozenset({"scraper_headers"})

    async def get_by_name(self, name: str) -> ScraperHeader | None:
        stmt = select(ScraperHeader).where(ScraperHeader.name == name)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_all(self) -> list[ScraperHeader]:
        stmt = select(ScraperHeader).order_by(ScraperHeader.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
