from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import sqlalchemy as sa
from httpx import AsyncClient

from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.password import hash_password
from app.main import app
from app.models.attribute import Attribute
from app.models.attribute_group import AttributeGroup
from app.models.product_type import ProductType
from app.models.search_eval import SearchEvalJudgment, SearchEvalQuery
from app.models.user import User


def _gen_ok() -> dict:
    return {"status": "ok", "queries": [{"text": f"silk dress {_uid()}", "locale": "en"}, {"text": f"فستان حرير {_uid()}", "locale": "ar"}]}


SEARCH_OK = {
    "status": "ok",
    "rewritten_query": "silk dress",
    "filters": {"_material": ["silk"]},
    "specs": [{"query": "silk dress", "filters": {"_material": ["silk"]}}],
    "results": [
        {
            "rank": 1,
            "score": 0.82,
            "product": {
                "id": "prod-1",
                "name": "Silk Dress",
                "price": 250.0,
                "currency": "SAR",
                "brand": "Zara",
                "image_url": "product-graph/x.jpg",
                "store_id": "store-1",
            },
        }
    ],
}


def _mock_ai_client(**kwargs: object) -> MagicMock:
    mock = MagicMock()
    mock.eval_generate_queries = AsyncMock(return_value=kwargs.get("eval_generate_queries", _gen_ok()))
    mock.eval_search = AsyncMock(return_value=kwargs.get("eval_search", SEARCH_OK))
    return mock


def _uid() -> str:
    return str(uuid.uuid4())


async def _db_admin_headers(db_session) -> dict[str, str]:
    """Admin token backed by a unique user — safe when the endpoint commits the session."""
    user = User(
        email=f"admin-{_uid()}@example.com",
        username=f"admin-{_uid()}",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin User",
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


class TestGenerateQueries:
    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/v1/admin/search-eval/queries/generate", json={"count": 5})
        assert resp.status_code == 401

    async def test_forbidden(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/admin/search-eval/queries/generate", json={"count": 5}, headers=auth_headers)
        assert resp.status_code == 403

    async def test_success_persists_llm_rows(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        mock = _mock_ai_client()
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post(
                "/api/v1/admin/search-eval/queries/generate",
                json={"count": 10, "locales": ["en", "ar"]},
                headers=headers,
            )
        finally:
            app.state.ai_client = original

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert {item["locale"] for item in data} == {"en", "ar"}
        assert all(item["source"] == "llm" for item in data)
        assert all(item["status"] == "pending" for item in data)
        mock.eval_generate_queries.assert_awaited_once()
        await db_session.flush()
        rows = (await db_session.execute(sa.select(SearchEvalQuery))).scalars().all()
        assert len(rows) == 2

    async def test_skips_duplicates(self, client: AsyncClient, db_session):
        dup_text = f"silk dress {_uid()}"
        db_session.add(SearchEvalQuery(id=_uid(), text=dup_text, locale="en", source="manual", status="pending"))
        await db_session.flush()
        headers = await _db_admin_headers(db_session)
        mock = _mock_ai_client(eval_generate_queries={"status": "ok", "queries": [{"text": dup_text, "locale": "en"}]})
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post("/api/v1/admin/search-eval/queries/generate", json={"count": 10}, headers=headers)
        finally:
            app.state.ai_client = original

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 0

    async def test_engine_error(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        mock = _mock_ai_client(eval_generate_queries={"status": "error", "reason": "llm failed"})
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post("/api/v1/admin/search-eval/queries/generate", json={"count": 10}, headers=headers)
        finally:
            app.state.ai_client = original

        assert resp.status_code == 503

    async def test_engine_unreachable(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        mock = _mock_ai_client(eval_generate_queries=None)
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post("/api/v1/admin/search-eval/queries/generate", json={"count": 10}, headers=headers)
        finally:
            app.state.ai_client = original

        assert resp.status_code == 503

    async def test_catalog_context_built_from_db(self, client: AsyncClient, db_session):
        group = AttributeGroup(id=_uid(), code=f"grp-{_uid()}", name_en="Fit", name_ar="المقاس", name_fa="سایز")
        db_session.add(group)
        db_session.add(ProductType(id=_uid(), name_en="Dresses", name_ar="فساتين", name_fa="لباس", code=f"dress-{_uid()}"))
        db_session.add(
            Attribute(
                id=_uid(),
                group_id=group.id,
                code="sleeve",
                name_en="Sleeve",
                name_ar="الكم",
                name_fa="آستین",
                value_type="string",
                input_type="select",
                is_search_affecting=True,
            )
        )
        await db_session.flush()

        headers = await _db_admin_headers(db_session)
        mock = _mock_ai_client()
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post("/api/v1/admin/search-eval/queries/generate", json={"count": 10}, headers=headers)
        finally:
            app.state.ai_client = original

        assert resp.status_code == 200
        context = mock.eval_generate_queries.await_args.args[2]
        assert "Dresses" in context
        assert "فساتين" in context
        assert "Sleeve" in context
        assert "الكم" in context


class TestImportQueries:
    async def test_import_creates_queries_and_judgments(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        text = f"black sneakers {_uid()}"
        resp = await client.post(
            "/api/v1/admin/search-eval/queries/import",
            json={"queries": [{"text": text, "locale": "en", "relevant_ids": ["p1", "p2"]}]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == {"created": 1, "skipped": 0, "judgments_created": 2}

        await db_session.flush()
        query = (await db_session.execute(sa.select(SearchEvalQuery).where(SearchEvalQuery.text == text))).scalar_one()
        assert query.source == "seed"
        assert query.status == "evaluated"
        judgments = (await db_session.execute(sa.select(SearchEvalJudgment).where(SearchEvalJudgment.query_id == query.id))).scalars().all()
        assert len(judgments) == 2
        assert all(j.relevant for j in judgments)

    async def test_import_skips_existing(self, client: AsyncClient, db_session):
        text = f"black sneakers {_uid()}"
        db_session.add(SearchEvalQuery(id=_uid(), text=text, locale="en", source="manual", status="pending"))
        await db_session.flush()
        headers = await _db_admin_headers(db_session)
        resp = await client.post(
            "/api/v1/admin/search-eval/queries/import",
            json={"queries": [{"text": text, "locale": "en", "relevant_ids": ["p1"]}]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == {"created": 0, "skipped": 1, "judgments_created": 1}


class TestListQueries:
    async def test_list_with_filters(self, client: AsyncClient, db_session):
        prefix = f"zzz-{_uid()}"
        db_session.add_all(
            [
                SearchEvalQuery(id=_uid(), text=f"{prefix} silk", locale="en", source="llm", status="pending"),
                SearchEvalQuery(id=_uid(), text=f"{prefix} shoes", locale="en", source="seed", status="evaluated"),
                SearchEvalQuery(id=_uid(), text=f"{prefix} فستان", locale="ar", source="manual", status="pending"),
            ]
        )
        await db_session.flush()
        headers = await _db_admin_headers(db_session)

        resp = await client.get(f"/api/v1/admin/search-eval/queries?q={prefix}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 3
        assert len(body["data"]["items"]) == 3

        resp = await client.get(f"/api/v1/admin/search-eval/queries?q={prefix}&locale=ar&status=pending", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["text"] == f"{prefix} فستان"

        resp = await client.get(f"/api/v1/admin/search-eval/queries?q={prefix}&source=seed", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["text"] == f"{prefix} shoes"

    async def test_list_requires_admin(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/admin/search-eval/queries", headers=auth_headers)
        assert resp.status_code == 403


class TestUpdateQuery:
    async def test_update_status(self, client: AsyncClient, db_session):
        qid = _uid()
        db_session.add(SearchEvalQuery(id=qid, text=f"silk dress {_uid()}", locale="en", source="manual", status="pending"))
        await db_session.flush()
        headers = await _db_admin_headers(db_session)
        resp = await client.patch(
            f"/api/v1/admin/search-eval/queries/{qid}",
            json={"status": "skipped"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "skipped"

    async def test_update_not_found(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        resp = await client.patch(
            "/api/v1/admin/search-eval/queries/nope",
            json={"status": "skipped"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestSaveJudgments:
    async def test_save_marks_evaluated(self, client: AsyncClient, db_session):
        qid = _uid()
        db_session.add(SearchEvalQuery(id=qid, text=f"silk dress {_uid()}", locale="en", source="manual", status="pending"))
        await db_session.flush()
        headers = await _db_admin_headers(db_session)
        resp = await client.put(
            f"/api/v1/admin/search-eval/queries/{qid}/judgments",
            json={
                "judgments": [
                    {"product_id": "p1", "relevant": True, "rank": 1},
                    {"product_id": "p2", "relevant": False, "rank": 2},
                ]
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "evaluated"

        await db_session.flush()
        judgments = (await db_session.execute(sa.select(SearchEvalJudgment).where(SearchEvalJudgment.query_id == qid))).scalars().all()
        assert len(judgments) == 2

    async def test_replace_judgments(self, client: AsyncClient, db_session):
        qid = _uid()
        db_session.add(SearchEvalQuery(id=qid, text=f"silk dress {_uid()}", locale="en", source="manual", status="pending"))
        await db_session.flush()
        db_session.add(SearchEvalJudgment(id=_uid(), query_id=qid, product_id="old", relevant=True, rank=1))
        await db_session.flush()
        headers = await _db_admin_headers(db_session)
        resp = await client.put(
            f"/api/v1/admin/search-eval/queries/{qid}/judgments",
            json={"judgments": [{"product_id": "new", "relevant": True, "rank": 1}]},
            headers=headers,
        )
        assert resp.status_code == 200
        await db_session.flush()
        judgments = (await db_session.execute(sa.select(SearchEvalJudgment).where(SearchEvalJudgment.query_id == qid))).scalars().all()
        assert [j.product_id for j in judgments] == ["new"]


class TestMetrics:
    async def test_metrics_math(self, client: AsyncClient, db_session):
        await db_session.execute(sa.delete(SearchEvalJudgment))
        await db_session.execute(sa.delete(SearchEvalQuery))
        await db_session.flush()
        q1, q2 = _uid(), _uid()
        db_session.add_all(
            [
                SearchEvalQuery(id=q1, text=f"silk dress {_uid()}", locale="en", source="manual", status="evaluated"),
                SearchEvalQuery(id=q2, text=f"black shoes {_uid()}", locale="en", source="manual", status="evaluated"),
                SearchEvalQuery(id=_uid(), text=f"فستان {_uid()}", locale="ar", source="manual", status="pending"),
            ]
        )
        await db_session.flush()
        db_session.add_all(
            [
                # q1: first relevant at rank 3 → MRR 1/3; recall 2/3 (ranks 3, 7)
                SearchEvalJudgment(id=_uid(), query_id=q1, product_id="a", relevant=True, rank=3),
                SearchEvalJudgment(id=_uid(), query_id=q1, product_id="b", relevant=True, rank=7),
                SearchEvalJudgment(id=_uid(), query_id=q1, product_id="c", relevant=False, rank=1),
                # q2: first relevant at rank 1 → MRR 1; recall 1/2 (rank 1, 12)
                SearchEvalJudgment(id=_uid(), query_id=q2, product_id="d", relevant=True, rank=1),
                SearchEvalJudgment(id=_uid(), query_id=q2, product_id="e", relevant=True, rank=12),
            ]
        )
        await db_session.flush()
        headers = await _db_admin_headers(db_session)

        resp = await client.get("/api/v1/admin/search-eval/metrics", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        overall = data["overall"]
        assert overall["query_count"] == 2
        assert overall["mrr_10"] == round(((1 / 3) + 1.0) / 2, 4)
        assert overall["recall_10"] == round(((2 / 2) + (1 / 2)) / 2, 4)
        by_locale = {m["locale"]: m for m in data["per_locale"]}
        assert by_locale["en"]["query_count"] == 2
        assert by_locale["ar"]["query_count"] == 0
        assert by_locale["ar"]["mrr_10"] == 0.0

    async def test_metrics_empty(self, client: AsyncClient, db_session):
        await db_session.execute(sa.delete(SearchEvalJudgment))
        await db_session.execute(sa.delete(SearchEvalQuery))
        await db_session.flush()
        headers = await _db_admin_headers(db_session)
        resp = await client.get("/api/v1/admin/search-eval/metrics", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["overall"] == {"locale": "all", "query_count": 0, "mrr_10": 0.0, "recall_10": 0.0}


class TestEvalSearch:
    async def test_search_success(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        mock = _mock_ai_client()
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post(
                "/api/v1/admin/search-eval/search",
                json={"query": "silk dress", "locale": "en", "limit": 10},
                headers=headers,
            )
        finally:
            app.state.ai_client = original

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["rewritten_query"] == "silk dress"
        assert data["filters"] == {"_material": ["silk"]}
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["rank"] == 1
        assert result["score"] == 0.82
        assert result["id"] == "prod-1"
        assert result["name"] == "Silk Dress"
        assert result["image_url"] == f"{settings.minio_public_url}/product-graph/x.jpg"
        mock.eval_search.assert_awaited_once()
        assert mock.eval_search.await_args.args[0] == "silk dress"

    async def test_search_engine_error(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        mock = _mock_ai_client(eval_search=None)
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post(
                "/api/v1/admin/search-eval/search",
                json={"query": "silk dress"},
                headers=headers,
            )
        finally:
            app.state.ai_client = original

        assert resp.status_code == 503

    async def test_search_requires_admin(self, client: AsyncClient):
        resp = await client.post("/api/v1/admin/search-eval/search", json={"query": "dress"})
        assert resp.status_code == 401
