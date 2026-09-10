import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest, ChatResponse, ProductRef, SummarizeRequest, TitleRequest
from app.schemas.product import Attribute, DescriptionResponse, GenerateDescriptionRequest, ProductData


class TestProductData:
    def test_minimal(self) -> None:
        p = ProductData()
        assert p.name_en is None
        assert p.name_ar is None
        assert p.brand is None
        assert p.category_name is None
        assert p.image_alt_texts == []
        assert p.attributes == []
        assert p.price is None
        assert p.currency == "SAR"

    def test_full(self) -> None:
        p = ProductData(
            name_en="Test Product",
            name_ar="منتج تجريبي",
            brand="Test Brand",
            category_name="Tops",
            image_alt_texts=["Front view", "Back view"],
            attributes=[Attribute(name="color", value="red"), Attribute(name="size", value="M")],
            price=99.99,
            currency="USD",
        )
        assert p.name_en == "Test Product"
        assert p.name_ar == "منتج تجريبي"
        assert p.brand == "Test Brand"
        assert p.category_name == "Tops"
        assert p.image_alt_texts == ["Front view", "Back view"]
        assert len(p.attributes) == 2
        assert p.attributes[0].name == "color"
        assert p.attributes[0].value == "red"
        assert p.price == 99.99
        assert p.currency == "USD"

    def test_empty_attributes(self) -> None:
        p = ProductData(attributes=[])
        assert p.attributes == []


class TestAttribute:
    def test_basic(self) -> None:
        a = Attribute(name="Material", value="Cotton")
        assert a.name == "Material"
        assert a.value == "Cotton"


class TestGenerateDescriptionRequest:
    def test_without_prompt(self) -> None:
        product = ProductData(name_en="Test")
        req = GenerateDescriptionRequest(product=product)
        assert req.product.name_en == "Test"
        assert req.prompt is None

    def test_with_prompt(self) -> None:
        product = ProductData(name_en="Test")
        req = GenerateDescriptionRequest(product=product, prompt="Custom prompt")
        assert req.prompt == "Custom prompt"

    def test_missing_product(self) -> None:
        with pytest.raises(ValidationError):
            GenerateDescriptionRequest()  # type: ignore[call-arg]


class TestDescriptionResponse:
    def test_basic(self) -> None:
        resp = DescriptionResponse(descriptions={"en": "Hello", "ar": "مرحبا"}, model="gpt-4", tokens_used=100, prompt="some prompt")
        assert resp.descriptions["en"] == "Hello"
        assert resp.model == "gpt-4"
        assert resp.tokens_used == 100
        assert resp.prompt == "some prompt"

    def test_serialization(self) -> None:
        resp = DescriptionResponse(descriptions={"en": "Hi"}, model="m1", tokens_used=50, prompt="p")
        data = resp.model_dump()
        assert data == {"descriptions": {"en": "Hi"}, "model": "m1", "tokens_used": 50, "prompt": "p"}


class TestChatRequest:
    def test_defaults(self) -> None:
        req = ChatRequest(query="find me a dress")
        assert req.query == "find me a dress"
        assert req.locale == "en"
        assert req.limit == 10

    def test_custom_locale(self) -> None:
        req = ChatRequest(query="فستان", locale="ar", limit=3)
        assert req.query == "فستان"
        assert req.locale == "ar"
        assert req.limit == 3

    def test_optional_prompts(self) -> None:
        req = ChatRequest(
            query="find me a dress",
            parse_prompt="Strict parser. Query: {raw_query}",
            system_prompt="You are a stylist.",
        )
        assert req.parse_prompt == "Strict parser. Query: {raw_query}"
        assert req.system_prompt == "You are a stylist."
        assert ChatRequest(query="x").parse_prompt is None
        assert ChatRequest(query="x").system_prompt is None

    def test_missing_query(self) -> None:
        with pytest.raises(ValidationError):
            ChatRequest()  # type: ignore[call-arg]


class TestChatResponse:
    def test_basic(self) -> None:
        resp = ChatResponse(answer="Here is a dress", products=[])
        assert resp.answer == "Here is a dress"
        assert resp.products == []

    def test_with_products(self) -> None:
        products = [ProductRef(id="p1", name="Dress", price=50.0)]
        resp = ChatResponse(answer="Found this", products=products)
        assert len(resp.products) == 1
        assert resp.products[0].id == "p1"
        assert resp.products[0].name == "Dress"

    def test_serialization(self) -> None:
        products = [ProductRef(id="p1", name="Dress", price=50.0, currency="SAR", brand="Zara")]
        resp = ChatResponse(answer="Found", products=products)
        data = resp.model_dump()
        assert data["answer"] == "Found"
        assert data["products"][0]["id"] == "p1"
        assert data["products"][0]["price"] == 50.0


class TestProductRef:
    def test_minimal(self) -> None:
        p = ProductRef(id="123")
        assert p.id == "123"
        assert p.name is None
        assert p.price is None
        assert p.currency == "SAR"
        assert p.brand is None
        assert p.image_url is None

    def test_full(self) -> None:
        p = ProductRef(id="123", name="Test", price=10.0, currency="USD", brand="Brand", image_url="http://example.com/img.jpg")
        assert p.name == "Test"
        assert p.price == 10.0
        assert p.currency == "USD"
        assert p.brand == "Brand"
        assert p.image_url == "http://example.com/img.jpg"


class TestSummarizeRequest:
    def test_defaults(self) -> None:
        req = SummarizeRequest(messages=[])
        assert req.messages == []
        assert req.previous_summary == ""
        assert req.locale == "en"
        assert req.prompt is None

    def test_custom(self) -> None:
        req = SummarizeRequest(
            messages=[{"role": "user", "content": "hi"}],
            previous_summary="prev",
            locale="ar",
            prompt="You summarize.\nPrevious:\n{previous_summary}\nHistory:\n{history_text}\n{locale_hint}",
        )
        assert req.previous_summary == "prev"
        assert req.locale == "ar"
        assert req.prompt is not None


class TestTitleRequest:
    def test_defaults(self) -> None:
        req = TitleRequest(query="red dress")
        assert req.locale == "en"
        assert req.prompt is None

    def test_custom(self) -> None:
        req = TitleRequest(query="فستان", locale="ar", prompt="Title it: {query}\n{locale_hint}")
        assert req.locale == "ar"
        assert req.prompt == "Title it: {query}\n{locale_hint}"
