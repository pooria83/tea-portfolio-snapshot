from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.services.chat_service import ChatService


class _FakeConversations:
    def __init__(self, doc: dict[str, Any] | None) -> None:
        self.doc = doc

    async def find_by_id_and_user(self, conversation_id: str, user_id: str) -> dict[str, Any] | None:
        return self.doc


class _FakeMessages:
    def __init__(self) -> None:
        self.created_args: tuple[object, ...] | None = None
        self.created_kwargs: dict[str, Any] | None = None

    async def create(self, *args: object, **kwargs: object) -> dict[str, Any]:
        self.created_args = args
        self.created_kwargs = dict(kwargs)
        return {"_id": "m1", **dict(kwargs)}


class _FakeAI:
    def __init__(self, result: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.last_call: dict[str, Any] | None = None

    async def similar_products(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = kwargs
        if self.error is not None:
            raise self.error
        return self.result or {}


class _FakeRow:
    def __init__(self, **fields: Any) -> None:
        self.__dict__.update(fields)


class _FakeResult:
    def __init__(self, row: Any = None, scalar: Any = None) -> None:
        self._row = row
        self._scalar = scalar

    def one_or_none(self) -> Any:
        return self._row

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _FakeSession:
    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = list(results)

    async def execute(self, _stmt: object) -> _FakeResult:
        return self._results.pop(0)


class _FakeCtx:
    def __init__(self, session: _FakeSession | None) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession | None:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeCtx:
        return _FakeCtx(self._session)


def _service(conversation: dict[str, Any] | None, ai: _FakeAI) -> tuple[ChatService, _FakeMessages]:
    svc = ChatService.__new__(ChatService)
    svc.conversations = _FakeConversations(conversation)  # type: ignore[assignment]
    messages = _FakeMessages()
    svc.messages = messages  # type: ignore[assignment]
    svc.ai_client = ai  # type: ignore[assignment]
    svc.session_factory = None
    return svc, messages


async def test_find_similar_persists_with_label_and_products():
    ai = _FakeAI(result={"products": [{"id": "p2", "name": "Similar", "image_url": "https://portfolio.example.invalid/x.jpg"}]})
    svc, messages = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "ar"}, ai)
    doc = await svc.find_similar("c1", "u1", "p1", product_name="فستان")

    assert doc["_id"] == "m1"
    assert messages.created_args is not None
    assert messages.created_args[0] == "c1"
    assert messages.created_args[1] == "assistant"
    assert messages.created_args[2] == "👆👆 هذه منتجات مشابهة لـ فستان"
    assert messages.created_kwargs is not None
    assert messages.created_kwargs["locale"] == "ar"
    snapshots = messages.created_kwargs["product_snapshots"]
    assert snapshots[0]["image_url"] == f"{settings.minio_public_url}/x.jpg"
    assert ai.last_call == {"product_id": "p1", "locale": "ar", "request_id": "", "user_id": "u1", "categories": None}


async def test_find_similar_label_includes_product_name_per_locale():
    ai = _FakeAI(result={"products": []})

    svc, messages = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "en"}, ai)
    await svc.find_similar("c1", "u1", "p1", product_name="Dress")
    assert messages.created_args is not None
    assert messages.created_args[2] == "👆👆 Here are similar products to Dress"

    svc, messages = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "fa"}, ai)
    await svc.find_similar("c1", "u1", "p1", product_name="پیراهن")
    assert messages.created_args is not None
    assert messages.created_args[2] == "👆👆 این محصولات مشابه پیراهن هستند"


async def test_find_similar_label_without_product_name_omits_blank():
    ai = _FakeAI(result={"products": []})
    svc, messages = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "en"}, ai)
    await svc.find_similar("c1", "u1", "p1")
    assert messages.created_args is not None
    assert messages.created_args[2] == "👆👆 Here are similar products to "


async def test_find_similar_missing_conversation():
    svc, _ = _service(None, _FakeAI(result={"products": []}))
    with pytest.raises(NotFoundError):
        await svc.find_similar("c1", "u1", "p1")


async def test_find_similar_closed_conversation():
    svc, _ = _service({"_id": "c1", "userId": "u1", "status": "closed", "locale": "en"}, _FakeAI(result={"products": []}))
    with pytest.raises(ConflictError):
        await svc.find_similar("c1", "u1", "p1")


async def test_find_similar_engine_not_found_raises_not_found():
    ai = _FakeAI(error=NotFoundError("not in index"))
    svc, _ = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "en"}, ai)
    with pytest.raises(NotFoundError):
        await svc.find_similar("c1", "u1", "p1")


async def test_find_similar_engine_failure_raises_unavailable():
    ai = _FakeAI(error=RuntimeError("boom"))
    svc, _ = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "en"}, ai)
    with pytest.raises(ServiceUnavailableError):
        await svc.find_similar("c1", "u1", "p1")


async def test_find_similar_forwards_bilingual_category_chain():
    ai = _FakeAI(result={"products": [{"id": "p2"}]})
    svc, _ = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "en"}, ai)
    svc.session_factory = _FakeFactory(_FakeSession([]))  # type: ignore[assignment]
    with (
        patch("app.services.chat_service.StoreProductRepository") as sp_repo,
        patch("app.services.chat_service.CategoryRepository") as cat_repo,
    ):
        sp_repo.return_value.get_category_id = AsyncMock(return_value="cat-leaves")
        sp_repo.return_value.list_names_brands = AsyncMock(return_value=[])
        cat_repo.return_value.get_chain = AsyncMock(
            return_value=[
                ("cat-leaves", "Dresses", "فساتين", "cat-women"),
                ("cat-women", "Women", "نساء", None),
            ]
        )
        await svc.find_similar("c1", "u1", "p1")
    assert ai.last_call is not None
    assert ai.last_call["categories"] == [["Dresses", "فساتين"], ["Women", "نساء"]]


async def test_find_similar_chain_lookup_failure_falls_back_to_none():
    ai = _FakeAI(result={"products": []})

    class _BoomCtx:
        async def __aenter__(self) -> None:
            raise RuntimeError("db down")

        async def __aexit__(self, *exc: object) -> bool:
            return False

    class _BoomFactory:
        def __call__(self) -> _BoomCtx:
            return _BoomCtx()

    svc, _ = _service({"_id": "c1", "userId": "u1", "status": "active", "locale": "en"}, ai)
    svc.session_factory = _BoomFactory()  # type: ignore[assignment]
    await svc.find_similar("c1", "u1", "p1")
    assert ai.last_call is not None
    assert ai.last_call["categories"] is None
