from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.schemas.chat import ProductRef

SIMILAR_PRODUCTS = [
    ProductRef(id="p9", name="Similar 1", price=9.0, currency="SAR", brand="Brand C", image_url="https://portfolio.example.invalid/product-graph/s1.jpg", store_id="st1"),
    ProductRef(id="p10", name="Similar 2", price=19.0, currency="SAR", brand="Brand D", image_url="https://portfolio.example.invalid/product-graph/s2.jpg", store_id="st1"),
]


@pytest.fixture
def similar_products() -> list[ProductRef]:
    return SIMILAR_PRODUCTS


async def test_similar_returns_products(
    test_client: AsyncClient,
    mock_rag: Any,
    similar_products: list[ProductRef],
) -> None:
    mock_rag.similar = AsyncMock(return_value=similar_products)
    resp = await test_client.post("/similar", json={"product_id": "p1", "lang": "en", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["products"]) == 2
    first = body["products"][0]
    assert first["id"] == "p9"
    assert first["name"] == "Similar 1"
    assert first["price"] == 9.0
    assert first["currency"] == "SAR"
    assert first["brand"] == "Brand C"
    assert first["image_url"] == "https://portfolio.example.invalid/product-graph/s1.jpg"
    assert first["store_id"] == "st1"


async def test_similar_defaults(test_client: AsyncClient, mock_rag: Any, similar_products: list[ProductRef]) -> None:
    mock_rag.similar = AsyncMock(return_value=similar_products)
    resp = await test_client.post("/similar", json={"product_id": "p1"})
    assert resp.status_code == 200
    mock_rag.similar.assert_awaited_once_with("p1", limit=10, categories=None, lang="en")


async def test_similar_404_when_not_indexed(test_client: AsyncClient, mock_rag: Any) -> None:
    mock_rag.similar = AsyncMock(return_value=[])
    resp = await test_client.post("/similar", json={"product_id": "missing"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_similar_rejects_invalid_limit(test_client: AsyncClient) -> None:
    resp = await test_client.post("/similar", json={"product_id": "p1", "limit": 0})
    assert resp.status_code == 422


async def test_similar_rejects_missing_product_id(test_client: AsyncClient) -> None:
    resp = await test_client.post("/similar", json={})
    assert resp.status_code == 422
