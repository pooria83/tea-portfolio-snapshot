from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.store_member import StoreMember
from app.models.user import User


@pytest.mark.asyncio
async def test_store_member_repo_get_by_store():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    members = [MagicMock(spec=StoreMember), MagicMock(spec=StoreMember)]
    mock_result.unique.return_value.scalars.return_value.all.return_value = members
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.get_by_store("store-1")
    assert result == members
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_member_repo_get_by_store_empty():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.get_by_store("store-1")
    assert result == []


@pytest.mark.asyncio
async def test_store_member_repo_get_by_store_and_user_found():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    member = MagicMock(spec=StoreMember)
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = member
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.get_by_store_and_user("store-1", "user-1")
    assert result is member


@pytest.mark.asyncio
async def test_store_member_repo_get_by_store_and_user_not_found():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.get_by_store_and_user("store-1", "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_store_member_repo_find_user_by_phone_found():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    user = MagicMock(spec=User)
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.find_user_by_phone("+1234567890")
    assert result is user


@pytest.mark.asyncio
async def test_store_member_repo_find_user_by_phone_not_found():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.find_user_by_phone("+0000000000")
    assert result is None


@pytest.mark.asyncio
async def test_store_member_repo_find_user_by_email_found():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    user = MagicMock(spec=User)
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.find_user_by_email("test@example.com")
    assert result is user


@pytest.mark.asyncio
async def test_store_member_repo_find_user_by_email_not_found():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.find_user_by_email("none@example.com")
    assert result is None


@pytest.mark.asyncio
async def test_store_member_repo_is_last_owner_true_when_one():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    owner = MagicMock(spec=StoreMember)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [owner]
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.is_last_owner("store-1")
    assert result is True


@pytest.mark.asyncio
async def test_store_member_repo_is_last_owner_true_when_none():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.is_last_owner("store-1")
    assert result is True


@pytest.mark.asyncio
async def test_store_member_repo_is_last_owner_false():
    from app.repositories.store_member import StoreMemberRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = StoreMemberRepository(mock_db)
    result = await repo.is_last_owner("store-1")
    assert result is False
