from fastapi import APIRouter, Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import PaginationParams, ProductFilterParams, RateLimit, get_admin_user
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate
from app.services import product_service
from app.services.product_service import product_to_response

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/", response_model=ProductResponse, status_code=201, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def create_product(data: ProductCreate, db: AsyncSession = Depends(get_db), _: str = Security(get_admin_user)) -> Product:
    return await product_service.create_product(db, data)


@router.get("/", response_model=ProductListResponse, dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))])
async def list_products(
    pagination: PaginationParams = Depends(),
    filters: ProductFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> ProductListResponse:
    items, total = await product_service.list_products(db, pagination, filters)
    return ProductListResponse(
        items=[product_to_response(p) for p in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        has_next=(pagination.skip + pagination.limit) < total,
        has_previous=pagination.skip > 0,
    )


@router.get("/{product_id}", response_model=ProductResponse, dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))])
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)) -> Product:
    return await product_service.get_product(db, product_id)


@router.patch("/{product_id}", response_model=ProductResponse, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def update_product(product_id: str, data: ProductUpdate, db: AsyncSession = Depends(get_db), _: str = Security(get_admin_user)) -> Product:
    return await product_service.update_product(db, product_id, data)


@router.delete("/{product_id}", status_code=204, dependencies=[Depends(RateLimit(max_requests=20, window_seconds=60))])
async def delete_product(product_id: str, db: AsyncSession = Depends(get_db), _: str = Security(get_admin_user)) -> None:
    await product_service.delete_product(db, product_id)
