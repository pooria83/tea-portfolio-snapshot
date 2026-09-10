from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.schemas.product import ProductData

PRODUCT_DATA_KWARGS = {
    "name_en": "Silk Dress",
    "name_ar": "فستان حريري",
    "brand": "Zara",
    "category_name": "Dresses",
    "attributes": [{"name": "color", "value": "red"}, {"name": "material", "value": "silk"}],
    "price": 99.99,
    "currency": "SAR",
    "image_alt_texts": ["Front view", "Back view"],
}


class TestBuildProductText:
    def test_basic(self) -> None:
        from app.routers.description import _build_product_text

        product = ProductData(**PRODUCT_DATA_KWARGS)
        text = _build_product_text(product)
        assert "Name (EN): Silk Dress" in text
        assert "Name (AR): فستان حريري" in text
        assert "Brand: Zara" in text
        assert "Category: Dresses" in text
        assert "Image descriptions: Front view; Back view" in text
        assert "color: red" in text
        assert "material: silk" in text
        assert "Price: 99.99 SAR" in text

    def test_optional_fields_omitted_when_missing(self) -> None:
        from app.routers.description import _build_product_text

        product = ProductData(name_en="Minimal")
        text = _build_product_text(product)
        assert "Name (EN): Minimal" in text
        assert "Name (AR)" not in text
        assert "Brand" not in text
        assert "Category" not in text
        assert "Image descriptions" not in text
        assert "Attributes" not in text
        assert "Price" not in text

    def test_price_without_currency(self) -> None:
        from app.routers.description import _build_product_text

        product = ProductData(name_en="Test", price=50.0)
        text = _build_product_text(product)
        assert "Price: 50.0 SAR" in text

    def test_single_attribute(self) -> None:
        from app.routers.description import _build_product_text

        product = ProductData(name_en="Test", brand="Nike", attributes=[{"name": "color", "value": "blue"}])
        text = _build_product_text(product)
        assert "color: blue" in text


class TestResolveLlmForModel:
    async def test_uses_default_llm_when_model_matches(self, test_client: AsyncClient) -> None:
        payload = {"product": {"name_en": "Test"}, "model": "test-model"}
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 200

    async def test_502_when_db_engine_missing(self, test_client: AsyncClient) -> None:
        payload = {"product": {"name_en": "Test"}, "model": "other-model"}
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 502
        assert "no database connection" in resp.text

    async def test_502_when_model_unresolvable(self, test_app: FastAPI, test_client: AsyncClient) -> None:
        test_app.state.db_engine = MagicMock()
        test_app.state.settings = MagicMock()
        test_app.state.settings.llm_encryption_key = ""

        with patch("app.routers.description.resolve_model_info", AsyncMock(return_value=None)):
            payload = {"product": {"name_en": "Test"}, "model": "other-model"}
            resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 502
        assert "Could not resolve active API key" in resp.text

    async def test_custom_model_success_returns_model_name(
        self,
        test_app: FastAPI,
        test_client: AsyncClient,
        mock_openai_chat: AsyncMock,
        mock_openai_client: MagicMock,
    ) -> None:
        mock_openai_chat.choices = [MagicMock()]
        mock_openai_chat.choices[0].message.content = '{"en": "Desc", "ar": "وصف"}'
        mock_openai_chat.usage = MagicMock()
        mock_openai_chat.usage.total_tokens = 30

        test_app.state.db_engine = MagicMock()
        test_app.state.settings = MagicMock()
        test_app.state.settings.llm_encryption_key = ""

        with patch("app.routers.description.resolve_model_info", AsyncMock(return_value={"api_key": "custom-key", "base_url": "https://custom.api/v1"})):
            payload = {"product": {"name_en": "Test"}, "model": "custom-model"}
            resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "custom-model"
        assert data["descriptions"]["en"] == "Desc"


class TestDescriptionRouter:
    async def test_generate_success(self, test_client: AsyncClient) -> None:
        payload = {
            "product": {
                "name_en": "Silk Dress",
                "name_ar": "فستان حريري",
                "brand": "Zara",
                "category_name": "Dresses",
                "attributes": [{"name": "color", "value": "red"}],
                "price": 99.99,
                "currency": "SAR",
            }
        }
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["descriptions"]["en"] == "Desc EN"
        assert data["descriptions"]["ar"] == "Desc AR"
        assert data["model"] == "test-model"
        assert data["tokens_used"] == 50
        assert data["prompt"] == "full prompt"

    async def test_generate_with_custom_prompt(self, test_client: AsyncClient) -> None:
        payload = {
            "product": {"name_en": "Test"},
            "prompt": "Custom prompt text",
        }
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["descriptions"]["en"] == "Raw EN"
        assert data["descriptions"]["ar"] == "Raw AR"
        assert data["model"] == "test-model"
        assert data["tokens_used"] == 30
        assert data["prompt"] == "Custom prompt text"

    async def test_generate_with_empty_custom_prompt_falls_back(self, test_client: AsyncClient) -> None:
        payload = {
            "product": {"name_en": "Test"},
            "prompt": "",
        }
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["descriptions"]["en"] == "Desc EN"

    async def test_generate_502_on_none_result(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_descriptions.return_value = (None, 0, "prompt")

        payload = {"product": {"name_en": "Test"}}
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 502
        assert "Description generation failed" in resp.text

    async def test_generate_with_custom_prompt_502(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_with_raw_prompt.return_value = (None, 0)

        payload = {"product": {"name_en": "Test"}, "prompt": "Custom prompt"}
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 502

    async def test_missing_product_field(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/generate-description", json={})
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            ("name_en", "Product X", "Product X"),
            ("brand", "Nike", "Nike"),
            ("category_name", "Shoes", "Shoes"),
            ("currency", "USD", "USD"),
        ],
    )
    async def test_product_field_passthrough(
        self,
        test_client: AsyncClient,
        field: str,
        value: str,
        expected: str,
    ) -> None:
        payload = {"product": {"name_en": "Test", field: value}}
        resp = await test_client.post("/generate-description", json=payload)
        assert resp.status_code == 200
