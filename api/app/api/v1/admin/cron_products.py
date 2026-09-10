from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity_logger import log_activity
from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.error_codes import E
from app.core.exceptions import NotFoundError
from app.core.redis import get_redis
from app.core.response import APIResponse, paginated, success
from app.models.store_product import StoreProduct
from app.models.user import User
from app.repositories.embedding import ProductEmbeddingRepository
from app.repositories.product_definition import StoreProductRepository
from app.services.embedding_config import get_active_embedding_model
from app.services.embedding_cron import reindex_active_model

router = APIRouter(prefix="/admin/cron", tags=["admin-cron"])


class CronProductItem(BaseModel):
    id: str
    name_en: str | None
    name_ar: str | None
    name_fa: str | None
    sku: str | None
    status: str  # "pending" | "generated"
    last_generated_at: datetime | None
    model: str | None


class CronProductDetail(BaseModel):
    id: str
    name_en: str | None
    name_ar: str | None
    name_fa: str | None
    sku: str | None
    prompt: str | None
    description_en: str | None
    description_ar: str | None
    model: str | None
    generated_at: datetime | None


class EmbeddingCronProductItem(BaseModel):
    id: str
    name_en: str | None
    name_ar: str | None
    name_fa: str | None
    sku: str | None
    embedding_model: str | None
    embedding_status: str | None
    embedding_error: str | None
    updated_at: datetime | None


class ProductEmbeddingRow(BaseModel):
    model_name: str
    model_id: str | None
    embedding_status: str
    embedding_error: str | None
    updated_at: datetime | None


class EmbeddingCronProductDetail(BaseModel):
    id: str
    name_en: str | None
    name_ar: str | None
    name_fa: str | None
    sku: str | None
    embedding_text: str | None
    embeddings: list[ProductEmbeddingRow]


class CronSummary(BaseModel):
    class CronCounts(BaseModel):
        total: int
        pending: int = 0
        generated: int = 0

    llm: CronCounts


@router.get("/products")
async def list_cron_products(
    status: str | None = Query(None, description="Filter by status: pending or generated"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> APIResponse[list[CronProductItem]]:
    rows, total = await StoreProductRepository(db).list_cron_page(status, skip, limit)

    items = [
        CronProductItem(
            id=product.id,
            name_en=product.name_en,
            name_ar=product.name_ar,
            name_fa=product.name_fa,
            sku=product.sku,
            status="generated" if product.ai_description_en or product.ai_description_ar else "pending",
            last_generated_at=last_generated_at,
            model=model,
        )
        for product, last_generated_at, model in rows
    ]

    return paginated(items, total, skip, limit)


@router.get("/products/{product_id}")
async def get_cron_product_detail(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> APIResponse[CronProductDetail]:
    product = await StoreProductRepository(db).get_with_ai_versions(product_id)

    if product is None:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)

    versions = product.ai_description_versions
    latest = versions[0] if versions else None

    return success(
        CronProductDetail(
            id=product.id,
            name_en=product.name_en,
            name_ar=product.name_ar,
            name_fa=product.name_fa,
            sku=product.sku,
            prompt=latest.prompt if latest else None,
            description_en=latest.description_en if latest else None,
            description_ar=latest.description_ar if latest else None,
            model=latest.model if latest else None,
            generated_at=latest.created_at if latest else None,
        )
    )


def _embedding_text(product: StoreProduct) -> str | None:
    parts = [
        p
        for p in [
            product.name_en,
            product.short_description_en,
            product.long_description_en,
            product.ai_description_en,
        ]
        if p
    ]
    text = " ".join(parts).strip()
    return text if text else None


@router.get("/embedding-products/active-model")
async def get_active_embedding_model_endpoint(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[dict[str, str]]:
    active_model, _ = await get_active_embedding_model(db, redis)
    return success({"active_model": active_model})


@router.post("/embedding-products/reindex")
async def reindex_embeddings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[dict[str, object]]:
    active_model, _ = await get_active_embedding_model(db, redis)
    affected = await reindex_active_model(db, active_model)
    await db.commit()

    await log_activity(
        session_factory=request.app.state.session_factory,
        actor_type="admin",
        action="REINDEX",
        status_code=200,
        resource_type="cron",
        message=f"embedding reindex for model {active_model}: {affected} products",
        details={"model": active_model, "affected": affected},
        path="/admin/cron/embedding-products/reindex",
        method="POST",
    )
    return success({"affected": affected, "active_model": active_model})


@router.get("/embedding-products")
async def list_embedding_cron_products(
    embedding_status: str | None = Query(None, description="Filter by embedding_status: pending, generating, done, or error"),
    model: str | None = Query(None, description="Filter by embedding model name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> APIResponse[list[EmbeddingCronProductItem]]:
    rows, total = await ProductEmbeddingRepository(db).list_cron_page(embedding_status, model, skip, limit)

    items = [
        EmbeddingCronProductItem(
            id=product.id,
            name_en=product.name_en,
            name_ar=product.name_ar,
            name_fa=product.name_fa,
            sku=product.sku,
            embedding_model=embedding.model_name,
            embedding_status=embedding.embedding_status,
            embedding_error=embedding.embedding_error,
            updated_at=embedding.updated_at,
        )
        for product, embedding in rows
    ]

    return paginated(items, total, skip, limit)


@router.get("/embedding-products/{product_id}")
async def get_embedding_cron_product_detail(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> APIResponse[EmbeddingCronProductDetail]:
    product = await StoreProductRepository(db).get(product_id)

    if product is None:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)

    embeddings = await ProductEmbeddingRepository(db).list_by_product(product_id)

    return success(
        EmbeddingCronProductDetail(
            id=product.id,
            name_en=product.name_en,
            name_ar=product.name_ar,
            name_fa=product.name_fa,
            sku=product.sku,
            embedding_text=_embedding_text(product),
            embeddings=[
                ProductEmbeddingRow(
                    model_name=e.model_name,
                    model_id=e.model_id,
                    embedding_status=e.embedding_status,
                    embedding_error=e.embedding_error,
                    updated_at=e.updated_at,
                )
                for e in embeddings
            ],
        )
    )


@router.get("/summary")
async def get_cron_summary(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
) -> APIResponse[CronSummary]:
    total_llm, pending_llm = await StoreProductRepository(db).count_ai_description_status()

    return success(
        CronSummary(
            llm=CronSummary.CronCounts(
                total=total_llm,
                pending=pending_llm,
                generated=total_llm - pending_llm,
            ),
        )
    )
