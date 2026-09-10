from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.product_type import ProductType
from app.models.store import Store
from app.models.store_product import StoreProduct
from app.models.store_type import StoreType
from app.models.user import User
from app.repositories.product import ProductRepository
from app.repositories.product_definition import StoreProductRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository


class TestUserRepository:
    async def test_add_and_get(self, db_session: AsyncSession):
        repo = UserRepository(db_session)
        user = await repo.add(User(email="repo@test.com", username="repotest", hashed_password="hash"))
        fetched = await repo.get(user.id)
        assert fetched is not None
        assert fetched.email == "repo@test.com"

    async def test_get_by_email(self, db_session: AsyncSession):
        repo = UserRepository(db_session)
        await repo.add(User(email="find@test.com", username="finduser", hashed_password="hash"))
        found = await repo.get_by_email("find@test.com")
        assert found is not None
        assert found.username == "finduser"

    async def test_get_by_username(self, db_session: AsyncSession):
        repo = UserRepository(db_session)
        await repo.add(User(email="uname@test.com", username="uniquename", hashed_password="hash"))
        found = await repo.get_by_username("uniquename")
        assert found is not None
        assert found.email == "uname@test.com"

    async def test_email_or_username_exists(self, db_session: AsyncSession):
        repo = UserRepository(db_session)
        await repo.add(User(email="exists@test.com", username="existsuser", hashed_password="hash"))
        assert await repo.email_or_username_exists("exists@test.com", "other") is True
        assert await repo.email_or_username_exists("other@test.com", "existsuser") is True
        assert await repo.email_or_username_exists("new@test.com", "newuser") is False

    async def test_list_users(self, db_session: AsyncSession):
        repo = UserRepository(db_session)
        await repo.add(User(email="a@test.com", username="aa", hashed_password="h"))
        await repo.add(User(email="b@test.com", username="bb", hashed_password="h"))
        users = await repo.list()
        assert len(users) >= 2


class TestProductRepository:
    async def test_add_and_soft_delete(self, db_session: AsyncSession):
        repo = ProductRepository(db_session)
        product = await repo.add(Product(name="Test", price=10.0))
        assert product.is_active is True
        deleted = await repo.soft_delete(product.id)
        assert deleted is not None
        assert deleted.is_active is False

    async def test_get_active_excludes_deleted(self, db_session: AsyncSession):
        repo = ProductRepository(db_session)
        product = await repo.add(Product(name="Gone", price=5.0))
        await repo.soft_delete(product.id)
        fetched = await repo.get_active(product.id)
        assert fetched is None

    async def test_list_active(self, db_session: AsyncSession):
        repo = ProductRepository(db_session)
        await repo.add(Product(name="Active1", price=1.0))
        p2 = await repo.add(Product(name="Active2", price=2.0))
        await repo.soft_delete(p2.id)
        active = await repo.list_active()
        names = [p.name for p in active]
        assert "Active1" in names
        assert "Active2" not in names


class TestStoreProductRepository:
    async def test_delete_images(self, db_session: AsyncSession):
        repo = StoreProductRepository(db_session)
        owner = User(id="owner-img-test", email="owner@test.com", username="owner", hashed_password="hash")
        db_session.add(owner)
        st = StoreType(id="st-img-test", name_en="Retail", name_ar="Retail", name_fa="Retail", is_active=True)
        db_session.add(st)
        pt = ProductType(id="pt-img-test", code="img-test", name_en="ImgTest", name_ar="ImgTest", name_fa="ImgTest", sort_order=0)
        db_session.add(pt)
        cat = Category(id="cat-img-test", product_type_id="pt-img-test", name_en="Cat", name_ar="Cat", name_fa="Cat", sort_order=0, is_active=True)
        db_session.add(cat)
        await db_session.flush()
        s1 = Store(
            id="s1",
            owner_id="owner-img-test",
            name="Test Store",
            store_type_id="st-img-test",
            category_id="cat-img-test",
            phone="+966500000000",
            address="Test",
            location_lat=0.0,
            location_lng=0.0,
            country_code="KW",
            price_unit_code="KWD",
            is_active=True,
        )
        db_session.add(s1)
        await db_session.flush()
        await repo.add(StoreProduct(id="test-img-del", store_id="s1", product_type_id="pt-img-test"))
        db_session.add(ProductImage(id="img1", product_id="test-img-del", image_url="http://example.com/1.jpg"))
        db_session.add(ProductImage(id="img2", product_id="test-img-del", image_url="http://example.com/2.jpg"))
        await db_session.flush()
        await repo.delete_images("test-img-del")
        await db_session.flush()
        remaining = await db_session.execute(select(ProductImage).where(ProductImage.product_id == "test-img-del"))
        assert len(remaining.scalars().all()) == 0


class TestRefreshTokenRepository:
    async def test_get_valid_nonexistent(self, db_session: AsyncSession):
        repo = RefreshTokenRepository(db_session)
        token = await repo.get_valid("nonexistent")
        assert token is None
