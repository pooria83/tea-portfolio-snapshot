from sqlalchemy import delete, func, select

from app.models.search_eval import SearchEvalJudgment, SearchEvalQuery
from app.repositories.base import BaseRepository


class SearchEvalQueryRepository(BaseRepository[SearchEvalQuery]):
    model = SearchEvalQuery
    TOUCHES: frozenset[str] = frozenset({"search_eval_queries"})

    async def get_by_text_locale(self, text: str, locale: str) -> SearchEvalQuery | None:
        stmt = select(SearchEvalQuery).where(SearchEvalQuery.text == text, SearchEvalQuery.locale == locale)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        locale: str | None,
        source: str | None,
        status: str | None,
        q: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[SearchEvalQuery], int]:
        stmt = select(SearchEvalQuery)
        if locale:
            stmt = stmt.where(SearchEvalQuery.locale == locale)
        if source:
            stmt = stmt.where(SearchEvalQuery.source == source)
        if status:
            stmt = stmt.where(SearchEvalQuery.status == status)
        if q:
            stmt = stmt.where(SearchEvalQuery.text.ilike(f"%{q}%"))

        total_result = await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        total = int(total_result.scalar_one())
        result = await self.db.execute(stmt.order_by(SearchEvalQuery.created_at.desc()).offset(skip).limit(limit))
        return list(result.scalars().all()), total

    async def list_evaluated(self) -> list[SearchEvalQuery]:
        stmt = select(SearchEvalQuery).where(SearchEvalQuery.status == "evaluated").order_by(SearchEvalQuery.locale)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SearchEvalJudgmentRepository(BaseRepository[SearchEvalJudgment]):
    model = SearchEvalJudgment
    TOUCHES: frozenset[str] = frozenset({"search_eval_judgments"})

    async def get_by_query_product(self, query_id: str, product_id: str) -> SearchEvalJudgment | None:
        stmt = select(SearchEvalJudgment).where(SearchEvalJudgment.query_id == query_id, SearchEvalJudgment.product_id == product_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SearchEvalJudgment]:
        result = await self.db.execute(select(SearchEvalJudgment))
        return list(result.scalars().all())

    async def list_by_query_id(self, query_id: str) -> list[SearchEvalJudgment]:
        stmt = select(SearchEvalJudgment).where(SearchEvalJudgment.query_id == query_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_query_id(self, query_id: str) -> None:
        await self.db.execute(delete(SearchEvalJudgment).where(SearchEvalJudgment.query_id == query_id))
