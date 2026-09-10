from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import PaginationParams, RateLimit, get_authenticated_user
from app.core.redis import get_redis
from app.core.response import APIResponse, paginated, success
from app.models.store import Store
from app.models.store_member import StoreMember
from app.models.store_product import StoreProduct
from app.models.user import User
from app.repositories.reference import CountryRepository, CurrencyRepository
from app.schemas.country_currency import CountryItem, CurrencyItem
from app.schemas.product_definition import StoreProductListItem
from app.schemas.store import (
    ProductStatsResponse,
    StoreCreate,
    StoreListResponse,
    StoreMemberAddRequest,
    StoreMemberResponse,
    StoreMemberRole,
    StoreResponse,
    StoreUpdate,
    StoreWorkingHourResponse,
)
from app.services import product_definition_service, store_service
from app.services.storage_service import move_url_to_bucket

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("", response_model=APIResponse[list[StoreListResponse]], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def list_all_stores(user: User = Depends(get_authenticated_user), db: AsyncSession = Depends(get_db)) -> APIResponse[list[StoreListResponse]]:
    stores = await store_service.get_user_stores(db, user.id)
    items = [_store_to_list_response(s) for s in stores]
    return success(items)


@router.get("/my", response_model=APIResponse[list[StoreListResponse]], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def list_my_stores(user: User = Depends(get_authenticated_user), db: AsyncSession = Depends(get_db)) -> APIResponse[list[StoreListResponse]]:
    stores = await store_service.get_user_stores(db, user.id)
    items = [_store_to_list_response(s) for s in stores]
    return success(items)


@router.get("/my/products", response_model=APIResponse[list[StoreProductListItem]], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def list_my_products(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, min_length=1, description="Search by product name (English or Arabic)"),
    store_id: str | None = Query(None, description="Filter by specific store"),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[StoreProductListItem]]:
    stores = await store_service.get_user_stores(db, user.id)
    store_ids = [s.id for s in stores]
    if q:
        products, total = await product_definition_service.search_my_products_light(db, store_ids, q, skip=pagination.skip, limit=pagination.limit, store_id=store_id)
    else:
        products, total = await product_definition_service.list_my_products_light(db, store_ids, skip=pagination.skip, limit=pagination.limit, store_id=store_id)
    return paginated(
        items=[StoreProductListItem.model_validate(p) for p in products],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/my/products/stats", response_model=APIResponse[ProductStatsResponse], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def my_products_stats(
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[ProductStatsResponse]:
    stores = await store_service.get_user_stores(db, user.id)
    store_ids = [s.id for s in stores]
    stats = await product_definition_service.get_my_products_stats(db, redis, store_ids)
    return success(ProductStatsResponse(**stats))


@router.get("/countries", response_model=APIResponse[list[CountryItem]], dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))])
async def list_countries(db: AsyncSession = Depends(get_db), redis: AsyncRedis = Depends(get_redis)) -> APIResponse[list[CountryItem]]:
    countries = await CountryRepository(db, redis).list_dto()
    return success([CountryItem.model_validate(c) for c in countries])


@router.get("/currencies", response_model=APIResponse[list[CurrencyItem]], dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))])
async def list_currencies(db: AsyncSession = Depends(get_db), redis: AsyncRedis = Depends(get_redis)) -> APIResponse[list[CurrencyItem]]:
    currencies = await CurrencyRepository(db, redis).list_dto()
    return success([CurrencyItem.model_validate(c) for c in currencies])


@router.post("", response_model=APIResponse[StoreResponse], status_code=201, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def create_store(data: StoreCreate, request: Request, user: User = Depends(get_authenticated_user), db: AsyncSession = Depends(get_db)) -> APIResponse[StoreResponse]:
    store = await store_service.create_store(db, user.id, data)
    store = await _load_relations(db, store)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = store.id
        activity["message"] = f"user {user.id} create store {store.id} {store.name}"
    return success(_store_to_response(store, my_role="owner"))


@router.get("/{store_id}", response_model=APIResponse[StoreResponse], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def get_store(store_id: str, user: User = Depends(get_authenticated_user), db: AsyncSession = Depends(get_db)) -> APIResponse[StoreResponse]:
    store, role = await store_service.get_store(db, store_id, user.id)
    store = await _load_relations(db, store)
    active_count = await _active_products_count(db, store_id)
    members = await store_service.get_members(db, store_id, user.id)
    return success(_store_to_response(store, active_count=active_count, members=members, my_role=role))


@router.patch("/{store_id}", response_model=APIResponse[StoreResponse], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def update_store(
    store_id: str,
    data: StoreUpdate,
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StoreResponse]:
    if data.logo_url:
        temp_storage = getattr(request.app.state, "temp_storage", None)
        store_storage = getattr(request.app.state, "store_storage", None)
        data.logo_url = await move_url_to_bucket(data.logo_url, temp_storage, store_storage)
    store, role = await store_service.update_store(db, store_id, user.id, data)
    store = await _load_relations(db, store)
    active_count = await _active_products_count(db, store_id)
    members = await store_service.get_members(db, store_id, user.id)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = store_id
        activity["message"] = f"user {user.id} update store {store_id} {store.name}"
    return success(_store_to_response(store, active_count=active_count, members=members, my_role=role))


@router.delete("/{store_id}", response_model=APIResponse[dict[str, str]], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def delete_store(store_id: str, request: Request, user: User = Depends(get_authenticated_user), db: AsyncSession = Depends(get_db)) -> APIResponse[dict[str, str]]:
    await store_service.delete_store(db, store_id, user.id)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = store_id
        activity["action"] = "DELETE"
        activity["message"] = f"user {user.id} delete store {store_id}"
    return success({"message": "Store deleted successfully"})


@router.post("/{store_id}/members", response_model=APIResponse[StoreMemberResponse], status_code=201, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def add_store_member(
    store_id: str,
    data: StoreMemberAddRequest,
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StoreMemberResponse]:
    member = await store_service.add_member(db, store_id, user.id, data.phone, data.email, data.role.value)
    member = await _load_member_user(db, member)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = store_id
        activity["action"] = "ADD_MEMBER"
        activity["message"] = f"user {user.id} add member {member.user_id} to store {store_id}"
    return success(_member_to_response(member))


@router.delete("/{store_id}/members/{member_id}", response_model=APIResponse[dict[str, str]], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def remove_store_member(
    store_id: str,
    member_id: str,
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[dict[str, str]]:
    await store_service.remove_member(db, store_id, member_id, user.id)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = store_id
        activity["action"] = "REMOVE_MEMBER"
        activity["message"] = f"user {user.id} remove member {member_id} from store {store_id}"
    return success({"message": "Member removed successfully"})


@router.get("/{store_id}/members", response_model=APIResponse[list[StoreMemberResponse]], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def list_store_members(
    store_id: str,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[StoreMemberResponse]]:
    members = await store_service.get_members(db, store_id, user.id)
    members = [await _load_member_user(db, m) for m in members]
    return success([_member_to_response(m) for m in members])


async def _load_member_user(db: AsyncSession, member: StoreMember) -> StoreMember:
    stmt = select(StoreMember).options(selectinload(StoreMember.user)).where(StoreMember.id == member.id)
    result = await db.execute(stmt)
    loaded = result.unique().scalar_one_or_none()
    return loaded or member


def _member_to_response(member: StoreMember) -> StoreMemberResponse:
    return StoreMemberResponse(
        id=member.id,
        user_id=member.user_id,
        role=StoreMemberRole(member.role),
        full_name=member.user.full_name if member.user else None,
        phone=member.user.phone if member.user else None,
        email=member.user.email if member.user else None,
    )


async def _load_relations(db: AsyncSession, store: Store) -> Store:
    stmt = (
        select(Store)
        .options(
            selectinload(Store.category),
            selectinload(Store.store_type),
            selectinload(Store.country),
            selectinload(Store.price_unit),
            selectinload(Store.working_hours),
        )
        .where(Store.id == store.id)
    )
    result = await db.execute(stmt)
    loaded = result.unique().scalar_one_or_none()
    if loaded is None:
        return store
    return loaded


async def _active_products_count(db: AsyncSession, store_id: str) -> int:
    stmt = select(func.count()).select_from(StoreProduct).where(StoreProduct.store_id == store_id, StoreProduct.status == "active")
    result = await db.execute(stmt)
    return int(result.scalar_one())


def _store_to_list_response(store: Store) -> StoreListResponse:
    return StoreListResponse(
        id=store.id,
        name=store.name,
        country_code=store.country_code,
        price_unit_code=store.price_unit_code,
        country_name_ar=store.country.name_ar if store.country else "",
        country_name_en=store.country.name_en if store.country else "",
        country_name_fa=store.country.name_fa if store.country else "",
        currency_name_ar=store.price_unit.name_ar if store.price_unit else "",
        currency_name_en=store.price_unit.name_en if store.price_unit else "",
        currency_name_fa=store.price_unit.name_fa if store.price_unit else "",
        currency_symbol=store.price_unit.symbol if store.price_unit else "",
        category_name_ar=store.category.name_ar if store.category else "",
        category_name_en=store.category.name_en if store.category else "",
        category_name_fa=store.category.name_fa if store.category else "",
        store_type_name_ar=store.store_type.name_ar if store.store_type else "",
        store_type_name_en=store.store_type.name_en if store.store_type else "",
        store_type_name_fa=store.store_type.name_fa if store.store_type else "",
        logo_url=store.logo_url,
        is_active=store.is_active,
        created_at=store.created_at,
    )


def _store_to_response(store: Store, active_count: int = 0, members: list[StoreMember] | None = None, my_role: str | None = None) -> StoreResponse:
    return StoreResponse(
        id=store.id,
        owner_id=store.owner_id,
        name=store.name,
        category_id=store.category_id,
        store_type_id=store.store_type_id,
        description=store.description,
        phone=store.phone,
        logo_url=store.logo_url,
        address=store.address,
        location_lat=store.location_lat,
        location_lng=store.location_lng,
        website=store.website,
        instagram=store.instagram,
        is_active=store.is_active,
        country_code=store.country_code,
        price_unit_code=store.price_unit_code,
        country_name_ar=store.country.name_ar if store.country else "",
        country_name_en=store.country.name_en if store.country else "",
        country_name_fa=store.country.name_fa if store.country else "",
        currency_name_ar=store.price_unit.name_ar if store.price_unit else "",
        currency_name_en=store.price_unit.name_en if store.price_unit else "",
        currency_name_fa=store.price_unit.name_fa if store.price_unit else "",
        currency_symbol=store.price_unit.symbol if store.price_unit else "",
        active_products_count=active_count,
        created_at=store.created_at,
        updated_at=store.updated_at,
        category_name_ar=store.category.name_ar if store.category else "",
        category_name_en=store.category.name_en if store.category else "",
        category_name_fa=store.category.name_fa if store.category else "",
        store_type_name_ar=store.store_type.name_ar if store.store_type else "",
        store_type_name_en=store.store_type.name_en if store.store_type else "",
        store_type_name_fa=store.store_type.name_fa if store.store_type else "",
        working_hours=[
            StoreWorkingHourResponse(
                id=wh.id,
                day_of_week=wh.day_of_week,
                open_time=wh.open_time,
                close_time=wh.close_time,
                is_closed=wh.is_closed,
            )
            for wh in (store.working_hours or [])
        ],
        members=[
            StoreMemberResponse(
                id=m.id,
                user_id=m.user_id,
                role=StoreMemberRole(m.role),
                full_name=m.user.full_name if m.user else None,
                phone=m.user.phone if m.user else None,
                email=m.user.email if m.user else None,
            )
            for m in (members or [])
        ],
        my_role=StoreMemberRole(my_role) if my_role else None,
    )
