from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError


@pytest.mark.asyncio
async def test_create_store_success():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_owner_store_count.return_value = 0
        mock_repo.add.return_value = MagicMock(id="store-1", owner_id="owner-1")
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)

        from app.schemas.store import StoreCreate, StoreWorkingHourInput
        from app.services.store_service import create_store

        data = StoreCreate(
            name="My Store",
            category_id="cat-1",
            store_type_id="st-1",
            phone="+966500000000",
            address="Addr",
            location_lat=24.0,
            location_lng=46.0,
            country_code="KW",
            price_unit_code="KWD",
            working_hours=[
                StoreWorkingHourInput(day_of_week=0, open_time="09:00", close_time="18:00"),
            ],
        )
        result = await create_store(mock_db, "owner-1", data)
        assert result.id == "store-1"
        assert mock_db.add.call_count == 2
        mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_store_max_limit_reached():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_owner_store_count.return_value = 3
        mock_repo_cls.return_value = mock_repo

        from app.schemas.store import StoreCreate
        from app.services.store_service import create_store

        data = StoreCreate(
            name="My Store",
            category_id="cat-1",
            store_type_id="st-1",
            phone="+966500000000",
            address="Addr",
            location_lat=24.0,
            location_lng=46.0,
            country_code="KW",
            price_unit_code="KWD",
        )
        with pytest.raises(ConflictError, match="Maximum of 3 stores allowed"):
            await create_store(AsyncMock(), "owner-1", data)


@pytest.mark.asyncio
async def test_create_store_no_working_hours():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_owner_store_count.return_value = 0
        mock_repo.add.return_value = MagicMock(id="store-2", owner_id="owner-1")
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)

        from app.schemas.store import StoreCreate
        from app.services.store_service import create_store

        data = StoreCreate(
            name="No WH",
            category_id="cat-1",
            store_type_id="st-1",
            phone="+966500000000",
            address="Addr",
            location_lat=24.0,
            location_lng=46.0,
            country_code="KW",
            price_unit_code="KWD",
        )
        result = await create_store(mock_db, "owner-1", data)
        assert result.id == "store-2"
        assert mock_db.add.call_count == 1
        mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_store_success():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        store = MagicMock()
        store.id = "store-1"
        store.owner_id = "owner-1"
        store.is_active = True
        store.working_hours = []

        mock_repo = AsyncMock()
        mock_repo.get_with_relations.return_value = store
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)

        from app.schemas.store import StoreUpdate
        from app.services.store_service import update_store

        data = StoreUpdate(name="Updated Store")
        result_store, result_role = await update_store(mock_db, "store-1", "owner-1", data)
        assert result_store.name == "Updated Store"
        assert result_role == "owner"
        mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_store_not_found_wrong_owner():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_with_relations.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.schemas.store import StoreUpdate
        from app.services.store_service import update_store

        data = StoreUpdate(name="X")
        with pytest.raises(NotFoundError, match="Store not found"):
            await update_store(AsyncMock(), "store-1", "wrong-owner", data)


@pytest.mark.asyncio
async def test_update_store_inactive():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        store = MagicMock()
        store.owner_id = "owner-1"
        store.is_active = False

        mock_repo = AsyncMock()
        mock_repo.get_with_relations.return_value = store
        mock_repo_cls.return_value = mock_repo

        from app.schemas.store import StoreUpdate
        from app.services.store_service import update_store

        data = StoreUpdate(name="X")
        with pytest.raises(NotFoundError, match="Store not found"):
            await update_store(AsyncMock(), "store-1", "owner-1", data)


@pytest.mark.asyncio
async def test_update_store_replace_working_hours():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        old_wh = MagicMock()
        old_wh.id = "wh-1"
        store = MagicMock()
        store.id = "store-1"
        store.owner_id = "owner-1"
        store.is_active = True
        store.working_hours = [old_wh]

        mock_repo = AsyncMock()
        mock_repo.get_with_relations.return_value = store
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)

        from app.schemas.store import StoreUpdate, StoreWorkingHourInput
        from app.services.store_service import update_store

        data = StoreUpdate(
            working_hours=[
                StoreWorkingHourInput(day_of_week=1, open_time="10:00", close_time="17:00"),
            ],
        )
        await update_store(mock_db, "store-1", "owner-1", data)
        mock_db.delete.assert_called_once_with(old_wh)
        mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_store_success():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        store = MagicMock()
        store.owner_id = "owner-1"
        store.is_active = True

        mock_repo = AsyncMock()
        mock_repo.get.return_value = store
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)

        from app.services.store_service import delete_store

        await delete_store(mock_db, "store-1", "owner-1")
        assert store.is_active is False
        mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_store_not_found():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.store_service import delete_store

        with pytest.raises(NotFoundError, match="Store not found"):
            await delete_store(AsyncMock(), "store-1", "owner-1")


@pytest.mark.asyncio
async def test_delete_store_already_inactive():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        store = MagicMock()
        store.owner_id = "owner-1"
        store.is_active = False

        mock_repo = AsyncMock()
        mock_repo.get.return_value = store
        mock_repo_cls.return_value = mock_repo

        from app.services.store_service import delete_store

        with pytest.raises(NotFoundError, match="Store not found"):
            await delete_store(AsyncMock(), "store-1", "owner-1")


@pytest.mark.asyncio
async def test_get_store_success():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        store = MagicMock()
        store.owner_id = "owner-1"
        store.is_active = True

        mock_repo = AsyncMock()
        mock_repo.get_with_relations.return_value = store
        mock_repo_cls.return_value = mock_repo

        from app.services.store_service import get_store

        result_store, result_role = await get_store(AsyncMock(), "store-1", "owner-1")
        assert result_store is store
        assert result_role == "owner"


@pytest.mark.asyncio
async def test_get_store_not_found():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_with_relations.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.store_service import get_store

        with pytest.raises(NotFoundError, match="Store not found"):
            await get_store(AsyncMock(), "store-1", "wrong-owner")


@pytest.mark.asyncio
async def test_get_user_stores():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_by_user.return_value = [MagicMock(), MagicMock()]
        mock_repo_cls.return_value = mock_repo

        from app.services.store_service import get_user_stores

        result = await get_user_stores(AsyncMock(), "owner-1")
        assert len(result) == 2


@pytest.mark.asyncio
async def test_add_member_success():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls, patch("app.services.store_service.StoreMemberRepository") as mock_member_cls:
        store = MagicMock()
        store.id = "store-1"
        store.owner_id = "owner-1"
        store.is_active = True

        mock_repo = AsyncMock()
        mock_repo.get.return_value = store
        mock_repo_cls.return_value = mock_repo

        target_user = MagicMock()
        target_user.id = "user-2"

        mock_member = AsyncMock()
        mock_member.find_user_by_phone.return_value = target_user
        mock_member.get_by_store_and_user.return_value = None
        mock_member.add.return_value = MagicMock(id="member-1", store_id="store-1", user_id="user-2", role="manager")
        mock_member_cls.return_value = mock_member

        mock_db = AsyncMock(spec=AsyncSession)

        from app.services.store_service import add_member

        result = await add_member(mock_db, "store-1", "owner-1", "+966500000001", None, "manager")
        assert result.id == "member-1"
        mock_member.add.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_member_success():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls, patch("app.services.store_service.StoreMemberRepository") as mock_member_cls:
        store = MagicMock()
        store.id = "store-1"
        store.owner_id = "owner-1"
        store.is_active = True

        mock_repo = AsyncMock()
        mock_repo.get.return_value = store
        mock_repo_cls.return_value = mock_repo

        member = MagicMock()
        member.id = "member-2"
        member.store_id = "store-1"
        member.user_id = "user-2"
        member.role = "manager"

        mock_member_repo = AsyncMock()
        mock_member_repo.get.return_value = member
        mock_member_repo.is_last_owner.return_value = False
        mock_member_cls.return_value = mock_member_repo

        from app.services.store_service import remove_member

        await remove_member(AsyncMock(), "store-1", "member-2", "owner-1")
        mock_member_repo.delete.assert_awaited_once_with(member)


@pytest.mark.asyncio
async def test_remove_member_not_found():
    with patch("app.services.store_service.StoreRepository") as mock_repo_cls, patch("app.services.store_service.StoreMemberRepository") as mock_member_cls:
        store = MagicMock()
        store.id = "store-1"
        store.owner_id = "owner-1"
        store.is_active = True

        mock_repo = AsyncMock()
        mock_repo.get.return_value = store
        mock_repo_cls.return_value = mock_repo

        mock_member_repo = AsyncMock()
        mock_member_repo.get.return_value = None
        mock_member_cls.return_value = mock_member_repo

        from app.services.store_service import remove_member

        with pytest.raises(NotFoundError, match="Store member not found"):
            await remove_member(AsyncMock(), "store-1", "nonexistent", "owner-1")
