from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import E
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.store import Store
from app.models.store_member import StoreMember
from app.models.store_product import StoreProduct
from app.models.user import User
from app.models.working_hour import WorkingHour
from app.repositories.store import StoreRepository
from app.repositories.store_member import StoreMemberRepository
from app.schemas.store import StoreCreate, StoreUpdate

MAX_STORES_PER_OWNER = 3


async def _get_store_for_user(db: AsyncSession, store_id: str, user_id: str) -> tuple[Store, str]:
    repo = StoreRepository(db)
    store = await repo.get_with_relations(store_id)
    if not store or not store.is_active:
        raise NotFoundError("Store not found", translation_key=E.STORE_NOT_FOUND)

    if store.owner_id == user_id:
        return store, "owner"

    member_repo = StoreMemberRepository(db)
    member = await member_repo.get_by_store_and_user(store_id, user_id)
    if not member:
        raise NotFoundError("Store not found", translation_key=E.STORE_NOT_FOUND)

    return store, member.role


async def _get_store_for_owner(db: AsyncSession, store_id: str, user_id: str) -> Store:
    repo = StoreRepository(db)
    store = await repo.get(store_id)
    if not store or store.owner_id != user_id:
        raise NotFoundError("Store not found", translation_key=E.STORE_NOT_FOUND)
    if not store.is_active:
        raise NotFoundError("Store not found", translation_key=E.STORE_NOT_FOUND)
    return store


async def create_store(db: AsyncSession, owner_id: str, data: StoreCreate) -> Store:
    repo = StoreRepository(db)
    count = await repo.get_owner_store_count(owner_id)
    if count >= MAX_STORES_PER_OWNER:
        raise ConflictError(f"Maximum of {MAX_STORES_PER_OWNER} stores allowed per seller", translation_key=E.MAX_STORES_REACHED)

    store = Store(
        owner_id=owner_id,
        name=data.name,
        category_id=data.category_id,
        store_type_id=data.store_type_id,
        description=data.description,
        phone=data.phone,
        address=data.address,
        location_lat=data.location_lat,
        location_lng=data.location_lng,
        logo_url=data.logo_url,
        website=data.website,
        instagram=data.instagram,
        country_code=data.country_code,
        price_unit_code=data.price_unit_code,
    )
    store = await repo.add(store)

    for wh_input in data.working_hours:
        wh = WorkingHour(
            store_id=store.id,
            day_of_week=wh_input.day_of_week,
            open_time=wh_input.open_time,
            close_time=wh_input.close_time,
            is_closed=wh_input.is_closed,
        )
        db.add(wh)

    member = StoreMember(store_id=store.id, user_id=owner_id, role="owner")
    db.add(member)

    await db.flush()
    return store


async def update_store(db: AsyncSession, store_id: str, user_id: str, data: StoreUpdate) -> tuple[Store, str]:
    store, role = await _get_store_for_user(db, store_id, user_id)

    if data.price_unit_code is not None and data.price_unit_code != store.price_unit_code:
        active_count = await _count_active_products(db, store_id)
        if active_count > 0:
            raise ConflictError("Cannot change price unit: store has active products", translation_key=E.CANNOT_CHANGE_PRICE_UNIT)

    update_data = data.model_dump(exclude_unset=True, exclude={"working_hours"})
    for field, value in update_data.items():
        setattr(store, field, value)

    if data.working_hours is not None:
        for old_wh in store.working_hours:
            await db.delete(old_wh)
        for wh_input in data.working_hours:
            wh = WorkingHour(
                store_id=store.id,
                day_of_week=wh_input.day_of_week,
                open_time=wh_input.open_time,
                close_time=wh_input.close_time,
                is_closed=wh_input.is_closed,
            )
            db.add(wh)

    await db.flush()
    return store, role


async def delete_store(db: AsyncSession, store_id: str, user_id: str) -> None:
    store = await _get_store_for_owner(db, store_id, user_id)
    store.is_active = False
    await db.flush()


async def get_store(db: AsyncSession, store_id: str, user_id: str) -> tuple[Store, str]:
    return await _get_store_for_user(db, store_id, user_id)


async def get_user_stores(db: AsyncSession, user_id: str) -> list[Store]:
    repo = StoreRepository(db)
    return await repo.get_by_user(user_id)


async def add_member(
    db: AsyncSession,
    store_id: str,
    current_user_id: str,
    phone: str | None,
    email: str | None,
    role: str,
) -> StoreMember:
    await _get_store_for_owner(db, store_id, current_user_id)

    if not phone and not email:
        raise ValidationError("Either phone or email must be provided", translation_key=E.PHONE_OR_EMAIL_REQUIRED)

    member_repo = StoreMemberRepository(db)

    target_user: User | None = None
    if phone:
        target_user = await member_repo.find_user_by_phone(phone)
    if not target_user and email:
        target_user = await member_repo.find_user_by_email(email)

    if not target_user:
        raise NotFoundError("User not found", translation_key=E.USER_NOT_FOUND)

    existing = await member_repo.get_by_store_and_user(store_id, target_user.id)
    if existing:
        raise ConflictError("User is already a member of this store", translation_key=E.MEMBER_ALREADY_EXISTS)

    if target_user.id == current_user_id:
        raise ConflictError("Cannot add yourself as a member", translation_key=E.CANNOT_ADD_SELF)

    member = StoreMember(store_id=store_id, user_id=target_user.id, role=role)
    return await member_repo.add(member)


async def remove_member(db: AsyncSession, store_id: str, member_id: str, current_user_id: str) -> None:
    await _get_store_for_owner(db, store_id, current_user_id)

    member_repo = StoreMemberRepository(db)
    member = await member_repo.get(member_id)
    if not member or member.store_id != store_id:
        raise NotFoundError("Store member not found", translation_key=E.MEMBER_NOT_FOUND)

    if member.user_id == current_user_id:
        raise ConflictError("Cannot remove yourself as a member. Transfer ownership first.", translation_key=E.CANNOT_REMOVE_SELF)

    if member.role == "owner" and await member_repo.is_last_owner(store_id):
        raise ConflictError("Cannot remove the last owner of the store", translation_key=E.CANNOT_REMOVE_LAST_OWNER)

    await member_repo.delete(member)


async def get_members(db: AsyncSession, store_id: str, current_user_id: str) -> list[StoreMember]:
    await _get_store_for_user(db, store_id, current_user_id)
    member_repo = StoreMemberRepository(db)
    return await member_repo.get_by_store(store_id)


async def _count_active_products(db: AsyncSession, store_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(StoreProduct)
        .where(
            StoreProduct.store_id == store_id,
            StoreProduct.status == "active",
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0
