"""Load test for product-graph-api.

Usage:
    locust -f tests/load/locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, between, task

CLIENT_ID = "load-test-user"


class APIUser(HttpUser):
    wait_time = between(0.5, 3)

    def on_start(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{CLIENT_ID}@loadtest.com",
                "username": CLIENT_ID,
                "password": "LoadTest123!",
            },
        )
        if response.status_code == 201:
            data = response.json()
            self.token = data["access_token"]
        else:
            response = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": f"{CLIENT_ID}@loadtest.com",
                    "password": "LoadTest123!",
                },
            )
            self.token = response.json().get("access_token", "")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def list_products(self):
        self.client.get("/api/v1/products/", headers=self.headers)

    @task(3)
    def health_check(self):
        self.client.get("/api/v1/health")

    @task(2)
    def get_metrics(self):
        self.client.get("/api/v1/metrics")
