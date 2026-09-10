import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.cache import CacheKeys, cache_or_fetch
from app.models.embed_model import EmbedModel
from app.models.product_embedding import ProductEmbedding
from app.models.store_product import StoreProduct
from app.repositories.base import BaseRepository


class EmbedModelRepository(BaseRepository[EmbedModel]):
    model = EmbedModel
    TOUCHES: frozenset[str] = frozenset({"embed_models"})

    async def list_active(self) -> list[EmbedModel]:
        stmt = select(EmbedModel).where(EmbedModel.is_active == True).order_by(EmbedModel.display_name)  # noqa: E712
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_name(self, model_name: str) -> dict[str, str | bool] | None:
        """Cached DTO read. Callers only need existence/identity, never ORM rows."""

        async def _fetch() -> dict[str, str | bool] | None:
            stmt = select(EmbedModel).where(EmbedModel.model_name == model_name, EmbedModel.is_active == True)  # noqa: E712
            result = await self.db.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return {
                "id": model.id,
                "model_name": model.model_name,
                "display_name": model.display_name,
                "is_active": model.is_active,
            }

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, CacheKeys.embed_model_by_name(model_name), CacheKeys.EMBED_MODEL_BY_NAME.ttl, _fetch)

    async def exists_by_name(self, model_name: str) -> bool:
        result = await self.db.execute(select(EmbedModel).where(EmbedModel.model_name == model_name))
        return result.scalar_one_or_none() is not None

    async def get_id_by_name(self, model_name: str) -> str | None:
        stmt = select(EmbedModel.id).where(EmbedModel.model_name == model_name).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class ProductEmbeddingRepository(BaseRepository[ProductEmbedding]):
    model = ProductEmbedding
    TOUCHES: frozenset[str] = frozenset({"product_embeddings"})

    async def upsert_status(
        self,
        product_id: str,
        model_name: str,
        status: str,
        error: str | None = None,
        model_id: str | None = None,
    ) -> None:
        stmt = pg_insert(ProductEmbedding).values(
            id=str(uuid.uuid4()),
            product_id=product_id,
            model_id=model_id,
            model_name=model_name,
            embedding_status=status,
            embedding_error=error,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_product_embedding_product_model",
            set_={
                "embedding_status": stmt.excluded.embedding_status,
                "embedding_error": stmt.excluded.embedding_error,
                "updated_at": func.now(),
            },
        )
        await self.db.execute(stmt)

    async def ensure_active_model_rows(self, model_name: str) -> int:
        """Insert pending rows for products missing an active-model row."""
        result = cast(
            CursorResult[Any],
            await self.db.execute(
                text(
                    """
                INSERT INTO product_embeddings (id, product_id, model_id, model_name, embedding_status)
                SELECT md5(s.id || ':' || :model),
                       s.id,
                       em.id,
                       :model,
                       'pending'
                FROM store_products s
                LEFT JOIN embed_models em ON em.model_name = :model
                LEFT JOIN product_embeddings pe ON pe.product_id = s.id AND pe.model_name = :model
                WHERE pe.id IS NULL
                """
                ),
                {"model": model_name},
            ),
        )
        return result.rowcount if result.rowcount is not None else 0

    async def fetch_stale(self, model_name: str, stale_minutes: int, limit: int) -> list[dict[str, str]]:
        cutoff = datetime.now(UTC) - timedelta(minutes=stale_minutes)
        rows = await self.db.execute(
            text(
                """
                SELECT pe.product_id AS id
                FROM product_embeddings pe
                WHERE pe.model_name = :model
                  AND pe.embedding_status IN ('pending', 'generating')
                  AND pe.updated_at < :cutoff
                ORDER BY pe.updated_at ASC
                LIMIT :limit
                """
            ),
            {"model": model_name, "cutoff": cutoff, "limit": limit},
        )
        return [{"id": row[0]} for row in rows]

    async def fetch_unembedded(self, model_name: str, include_errors: bool, limit: int) -> list[dict[str, str]]:
        statuses = ["pending", "generating"]
        if include_errors:
            statuses.append("error")
        rows = await self.db.execute(
            text(
                """
                SELECT pe.product_id AS id
                FROM product_embeddings pe
                WHERE pe.model_name = :model
                  AND pe.embedding_status = ANY(:statuses)
                ORDER BY pe.updated_at ASC
                LIMIT :limit
                """
            ),
            {"model": model_name, "statuses": statuses, "limit": limit},
        )
        return [{"id": row[0]} for row in rows]

    async def reindex_model(self, model_name: str) -> int:
        """Mark every product as pending for the given model (insert or reset)."""
        result = cast(
            CursorResult[Any],
            await self.db.execute(
                text(
                    """
                INSERT INTO product_embeddings (id, product_id, model_id, model_name, embedding_status)
                SELECT md5(s.id || ':' || :model),
                       s.id,
                       em.id,
                       :model,
                       'pending'
                FROM store_products s
                LEFT JOIN embed_models em ON em.model_name = :model
                ON CONFLICT (product_id, model_name)
                DO UPDATE SET embedding_status = 'pending', embedding_error = NULL, updated_at = now()
                """
                ),
                {"model": model_name},
            ),
        )
        return result.rowcount if result.rowcount is not None else 0

    async def claim_row(
        self,
        product_id: str,
        model_name: str,
        stale_cutoff: datetime | None = None,
    ) -> bool:
        """Atomically claim a pending/generating/error row as 'generating'.

        Error rows are claimable so explicit retries (backfill with
        ``include_errors``) can resubmit them; routine cron paths never fetch
        error rows, so this only affects deliberate retry runs.
        """
        if stale_cutoff is None:
            cutoff_sql = "TRUE"
            params: dict[str, object] = {"pid": product_id, "model": model_name}
        else:
            cutoff_sql = "updated_at < :cutoff"
            params = {"pid": product_id, "model": model_name, "cutoff": stale_cutoff}
        result = cast(
            CursorResult[Any],
            await self.db.execute(
                text(
                    f"""
                    UPDATE product_embeddings
                    SET embedding_status = 'generating', updated_at = now()
                    WHERE product_id = :pid
                      AND model_name = :model
                      AND embedding_status IN ('pending', 'generating', 'error')
                      AND {cutoff_sql}
                    """
                ),
                params,
            ),
        )
        return (result.rowcount or 0) > 0

    async def list_by_product(self, product_id: str) -> list[ProductEmbedding]:
        stmt = select(ProductEmbedding).where(ProductEmbedding.product_id == product_id).order_by(ProductEmbedding.updated_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_cron_page(
        self,
        embedding_status: str | None,
        model: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[tuple[StoreProduct, ProductEmbedding]], int]:
        base = select(StoreProduct, ProductEmbedding).join(ProductEmbedding, ProductEmbedding.product_id == StoreProduct.id)
        if model:
            base = base.where(ProductEmbedding.model_name == model)
        if embedding_status:
            base = base.where(ProductEmbedding.embedding_status == embedding_status)

        total = int((await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
        query = base.order_by(ProductEmbedding.updated_at.desc()).offset(skip).limit(limit)
        rows = (await self.db.execute(query)).all()
        items: list[tuple[StoreProduct, ProductEmbedding]] = [(row.StoreProduct, row.ProductEmbedding) for row in rows]
        return items, total
