from httpx import AsyncClient


class TestCreateProduct:
    async def test_create_product(self, client: AsyncClient, admin_headers: dict[str, str]):
        response = await client.post("/api/v1/products/", json={"name": "Test Product", "description": "A test product", "price": 29.99, "category": "electronics"}, headers=admin_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Product"
        assert data["price"] == 29.99
        assert data["is_active"] is True
        assert data["source"] == "internal"

    async def test_create_product_minimal(self, client: AsyncClient, admin_headers: dict[str, str]):
        response = await client.post("/api/v1/products/", json={"name": "Minimal"}, headers=admin_headers)
        assert response.status_code == 201
        assert response.json()["name"] == "Minimal"

    async def test_create_product_with_buy_url(self, client: AsyncClient, admin_headers: dict[str, str]):
        response = await client.post("/api/v1/products/", json={"name": "Buyable", "price": 10.0, "buy_url": "https://example.com/buy"}, headers=admin_headers)
        assert response.status_code == 201
        assert response.json()["buy_url"] == "https://example.com/buy"


class TestListProducts:
    async def test_list_products(self, client: AsyncClient, admin_headers: dict[str, str]):
        await client.post("/api/v1/products/", json={"name": "A", "price": 10.0}, headers=admin_headers)
        await client.post("/api/v1/products/", json={"name": "B", "price": 20.0}, headers=admin_headers)
        response = await client.get("/api/v1/products/")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 2
        assert len(body["items"]) >= 2
        assert body["has_previous"] is False

    async def test_list_products_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/products/")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_list_products_pagination(self, client: AsyncClient, admin_headers: dict[str, str]):
        for i in range(5):
            await client.post("/api/v1/products/", json={"name": f"P{i}", "price": float(i)}, headers=admin_headers)
        response = await client.get("/api/v1/products/?skip=0&limit=2")
        body = response.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5
        assert body["has_next"] is True
        assert body["has_previous"] is False

    async def test_list_products_second_page(self, client: AsyncClient, admin_headers: dict[str, str]):
        for i in range(5):
            await client.post("/api/v1/products/", json={"name": f"Q{i}", "price": float(i)}, headers=admin_headers)
        response = await client.get("/api/v1/products/?skip=2&limit=2")
        body = response.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5
        assert body["has_next"] is True
        assert body["has_previous"] is True

    async def test_list_products_filter_by_category(self, client: AsyncClient, admin_headers: dict[str, str]):
        await client.post("/api/v1/products/", json={"name": "Phone", "category": "Electronics"}, headers=admin_headers)
        await client.post("/api/v1/products/", json={"name": "Shirt", "category": "Clothing"}, headers=admin_headers)
        response = await client.get("/api/v1/products/?category=Electronics")
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Phone"

    async def test_list_products_filter_by_price_range(self, client: AsyncClient, admin_headers: dict[str, str]):
        await client.post("/api/v1/products/", json={"name": "Cheap", "price": 5.0}, headers=admin_headers)
        await client.post("/api/v1/products/", json={"name": "Medium", "price": 25.0}, headers=admin_headers)
        await client.post("/api/v1/products/", json={"name": "Expensive", "price": 100.0}, headers=admin_headers)
        response = await client.get("/api/v1/products/?min_price=10&max_price=50")
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Medium"

    async def test_list_products_sort_by_price_asc(self, client: AsyncClient, admin_headers: dict[str, str]):
        await client.post("/api/v1/products/", json={"name": "B", "price": 20.0}, headers=admin_headers)
        await client.post("/api/v1/products/", json={"name": "A", "price": 10.0}, headers=admin_headers)
        response = await client.get("/api/v1/products/?sort_by=price&sort_order=asc&limit=10")
        body = response.json()
        assert body["items"][0]["price"] <= body["items"][1]["price"]


class TestGetProduct:
    async def test_get_product(self, client: AsyncClient, admin_headers: dict[str, str]):
        created = await client.post("/api/v1/products/", json={"name": "Specific", "price": 15.0}, headers=admin_headers)
        pid = created.json()["id"]
        response = await client.get(f"/api/v1/products/{pid}")
        assert response.status_code == 200
        assert response.json()["name"] == "Specific"

    async def test_get_product_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/products/non-existent-id")
        assert response.status_code == 404

    async def test_get_deleted_product(self, client: AsyncClient, admin_headers: dict[str, str]):
        created = await client.post("/api/v1/products/", json={"name": "ToDelete", "price": 5.0}, headers=admin_headers)
        pid = created.json()["id"]
        await client.delete(f"/api/v1/products/{pid}", headers=admin_headers)
        response = await client.get(f"/api/v1/products/{pid}")
        assert response.status_code == 404


class TestUpdateProduct:
    async def test_update_product(self, client: AsyncClient, admin_headers: dict[str, str]):
        created = await client.post("/api/v1/products/", json={"name": "Original", "price": 10.0}, headers=admin_headers)
        pid = created.json()["id"]
        response = await client.patch(f"/api/v1/products/{pid}", json={"name": "Updated", "price": 20.0}, headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"
        assert response.json()["price"] == 20.0

    async def test_update_not_found(self, client: AsyncClient, admin_headers: dict[str, str]):
        response = await client.patch("/api/v1/products/non-existent", json={"name": "Nope"}, headers=admin_headers)
        assert response.status_code == 404


class TestDeleteProduct:
    async def test_delete_product(self, client: AsyncClient, admin_headers: dict[str, str]):
        created = await client.post("/api/v1/products/", json={"name": "To Delete", "price": 5.0}, headers=admin_headers)
        pid = created.json()["id"]
        response = await client.delete(f"/api/v1/products/{pid}", headers=admin_headers)
        assert response.status_code == 204

    async def test_delete_not_found(self, client: AsyncClient, admin_headers: dict[str, str]):
        response = await client.delete("/api/v1/products/non-existent", headers=admin_headers)
        assert response.status_code == 404


class TestAdminGate:
    async def test_non_admin_cannot_create(self, client: AsyncClient, auth_headers: dict[str, str]):
        response = await client.post("/api/v1/products/", json={"name": "Nope"}, headers=auth_headers)
        assert response.status_code == 403

    async def test_non_admin_cannot_update(self, client: AsyncClient, admin_headers: dict[str, str], auth_headers: dict[str, str]):
        created = await client.post("/api/v1/products/", json={"name": "Original", "price": 10.0}, headers=admin_headers)
        pid = created.json()["id"]
        response = await client.patch(f"/api/v1/products/{pid}", json={"name": "Hacked"}, headers=auth_headers)
        assert response.status_code == 403

    async def test_non_admin_cannot_delete(self, client: AsyncClient, admin_headers: dict[str, str], auth_headers: dict[str, str]):
        created = await client.post("/api/v1/products/", json={"name": "Doomed", "price": 5.0}, headers=admin_headers)
        pid = created.json()["id"]
        response = await client.delete(f"/api/v1/products/{pid}", headers=auth_headers)
        assert response.status_code == 403

    async def test_list_products_requires_no_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/products/")
        assert response.status_code == 200
