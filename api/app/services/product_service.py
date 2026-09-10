from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import PaginationParams, ProductFilterParams
from app.core.error_codes import E
from app.core.exceptions import NotFoundError
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate


async def create_product(db: AsyncSession, data: ProductCreate) -> Product:
    repo = ProductRepository(db)
    return await repo.add(Product(**data.model_dump()))


async def get_product(db: AsyncSession, product_id: str) -> Product:
    repo = ProductRepository(db)
    product = await repo.get_active(product_id)
    if not product:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)
    return product


async def list_products(
    db: AsyncSession,
    pagination: PaginationParams,
    filters: ProductFilterParams | None = None,
) -> tuple[list[Product], int]:
    repo = ProductRepository(db)
    total = await repo.count_active(
        category=filters.category if filters else None,
        min_price=filters.min_price if filters else None,
        max_price=filters.max_price if filters else None,
    )
    items = await repo.list_active(
        skip=pagination.skip,
        limit=pagination.limit,
        category=filters.category if filters else None,
        min_price=filters.min_price if filters else None,
        max_price=filters.max_price if filters else None,
        sort_by=filters.sort_by if filters else "created_at",
        sort_order=filters.sort_order if filters else "desc",
    )
    return items, total


async def update_product(db: AsyncSession, product_id: str, data: ProductUpdate) -> Product:
    repo = ProductRepository(db)
    product = await repo.get(product_id)
    if not product:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.flush()
    return product


async def delete_product(db: AsyncSession, product_id: str) -> None:
    repo = ProductRepository(db)
    product = await repo.soft_delete(product_id)
    if not product:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)


def product_to_response(product: Product) -> ProductResponse:
    return ProductResponse.model_validate(product)
