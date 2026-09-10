from collections.abc import Mapping, Sequence
from typing import Any

from app.services.chat_service import ChatService


class _FakeConversations:
    def __init__(self) -> None:
        self.updated: tuple[str, str] | None = None

    async def claim_message_slot(self, conversation_id: str, user_id: str) -> dict[str, object]:
        return {
            "_id": conversation_id,
            "userId": user_id,
            "locale": "en",
            "summary": "",
            "userMessageCount": 1,
        }

    async def find_by_id_and_user(self, conversation_id: str, user_id: str) -> dict[str, object] | None:
        return None

    async def update_locale(self, conversation_id: str, locale: str) -> bool:
        self.updated = (conversation_id, locale)
        return True


class _FakeMessages:
    def __init__(self) -> None:
        self.created_kwargs: dict[str, Any] | None = None

    async def create(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.created_kwargs = dict(kwargs)
        return {"_id": "m1"}

    async def list_all_before(self, conversation_id: str) -> list[dict[str, object]]:
        return []


def _service(session_factory=None) -> tuple[ChatService, _FakeConversations]:
    conversations = _FakeConversations()
    svc = ChatService.__new__(ChatService)
    svc.conversations = conversations  # type: ignore[assignment]
    svc.messages = _FakeMessages()  # type: ignore[assignment]
    svc.session_factory = session_factory
    return svc, conversations


class _FakeResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def execute(self, statement: object) -> _FakeResult:
        return _FakeResult(self._rows)


def _product_rows(products: Sequence[Mapping[str, Any]]) -> list[tuple[object, ...]]:
    return [(str(p["id"]), f"{p['id']}_ar_name", f"{p['id']}_en_name", None, f"{p['id']}_ar_brand", f"{p['id']}_en_brand", None) for p in products]


async def test_claim_turn_detects_arabic_and_persists() -> None:
    svc, conversations = _service()

    _conversation, _user_message, _summary, _history, locale = await svc.claim_turn("u1", "c1", "هل عندكم توب صيفي؟")

    assert locale == "ar"
    assert conversations.updated == ("c1", "ar")


async def test_claim_turn_detects_farsi() -> None:
    svc, conversations = _service()

    _conversation, _user_message, _summary, _history, locale = await svc.claim_turn("u1", "c1", "پیراهن قرمز میخواهم")

    assert locale == "fa"
    assert conversations.updated == ("c1", "fa")


async def test_claim_turn_keeps_locale_for_english_message() -> None:
    svc, conversations = _service()

    _conversation, _user_message, _summary, _history, locale = await svc.claim_turn("u1", "c1", "Show me red dresses")

    assert locale == "en"
    assert conversations.updated is None


async def test_claim_turn_inconclusive_message_keeps_conversation_locale() -> None:
    svc, conversations = _service()

    _conversation, _user_message, _summary, _history, locale = await svc.claim_turn("u1", "c1", "🛍️")

    assert locale == "en"
    assert conversations.updated is None


async def test_enrich_product_names_attaches_localized_fields() -> None:
    products = [
        {"id": "p1", "name": "Blue Top", "brand": "Zara"},
        {"id": "p2", "name": "Red Dress", "brand": "Zara"},
    ]
    svc, _conversations = _service(session_factory=lambda: _FakeSession(_product_rows(products)))

    await svc.enrich_product_names(products)

    assert products[0]["name_ar"] == "p1_ar_name"
    assert products[0]["name_en"] == "p1_en_name"
    assert products[0]["brand_ar"] == "p1_ar_brand"
    assert products[0]["brand_en"] == "p1_en_brand"


async def test_enrich_product_names_keeps_unmatched_products_untouched() -> None:
    products = [{"id": "p1", "name": "Blue Top"}]
    rows = _product_rows([{"id": "other", "name": "X"}])
    svc, _conversations = _service(session_factory=lambda: _FakeSession(rows))

    await svc.enrich_product_names(products)

    assert "name_ar" not in products[0]


async def test_enrich_product_names_skips_already_enriched() -> None:
    products = [{"id": "p1", "name": "Blue Top", "name_ar": "توب أزرق"}]
    calls: list[object] = []

    def factory() -> object:
        calls.append(1)
        raise AssertionError("session must not be created for already-enriched cards")

    svc, _conversations = _service(session_factory=factory)

    await svc.enrich_product_names(products)

    assert calls == []


async def test_enrich_product_names_graceful_without_session_factory() -> None:
    products = [{"id": "p1", "name": "Blue Top"}]
    svc, _conversations = _service()

    await svc.enrich_product_names(products)

    assert "name_ar" not in products[0]


async def test_persist_assistant_snapshot_has_localized_names() -> None:
    products = [{"id": "p1", "name": "Blue Top", "brand": "Zara"}]
    rows = _product_rows(products)
    svc, _conversations = _service(session_factory=lambda: _FakeSession(rows))

    await svc.persist_assistant("c1", "answer", products)

    saved = svc.messages.created_kwargs  # type: ignore[attr-defined]
    snapshot = saved["product_snapshots"][0]
    assert snapshot["name_ar"] == "p1_ar_name"
    assert snapshot["name_en"] == "p1_en_name"
    assert snapshot["brand_ar"] == "p1_ar_brand"


async def test_persist_assistant_stores_locale_when_given() -> None:
    products = [{"id": "p1", "name": "Blue Top", "brand": "Zara"}]
    svc, _conversations = _service()

    await svc.persist_assistant("c1", "answer", products, locale="ar")

    saved = svc.messages.created_kwargs  # type: ignore[attr-defined]
    assert saved["locale"] == "ar"


async def test_persist_assistant_locale_empty_becomes_none() -> None:
    products = [{"id": "p1", "name": "Blue Top", "brand": "Zara"}]
    svc, _conversations = _service()

    await svc.persist_assistant("c1", "answer", products, locale="")

    saved = svc.messages.created_kwargs  # type: ignore[attr-defined]
    assert saved["locale"] is None
