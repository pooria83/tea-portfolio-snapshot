from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.repositories.base import BaseRepository


class Repo(BaseRepository[Product]):
    model = Product


@pytest.fixture
def repo() -> Repo:
    mock_db = AsyncMock(spec=AsyncSession)
    return Repo(mock_db)


@pytest.mark.asyncio
async def test_get(repo: Repo):
    repo.db.get.return_value = Product(id="p1", name="Test", price=10.0)
    result = await repo.get("p1")
    assert result is not None
    assert result.name == "Test"


@pytest.mark.asyncio
async def test_get_not_found(repo: Repo):
    repo.db.get.return_value = None
    result = await repo.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_add(repo: Repo):
    obj = Product(name="New", price=5.0)
    result = await repo.add(obj)
    repo.db.add.assert_called_once_with(obj)
    repo.db.flush.assert_awaited_once()
    assert result is obj


@pytest.mark.asyncio
async def test_delete(repo: Repo):
    obj = Product(id="p1", name="Test", price=10.0)
    await repo.delete(obj)
    repo.db.delete.assert_awaited_once_with(obj)
    repo.db.flush.assert_awaited_once()
