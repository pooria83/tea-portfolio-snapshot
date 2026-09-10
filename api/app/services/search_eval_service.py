import uuid
from typing import Any

from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIEngineClient
from app.core.cache import CacheKeys, cache_or_fetch, invalidate_tables
from app.core.error_codes import E
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.images import normalize_image_url
from app.models.search_eval import SearchEvalJudgment, SearchEvalQuery
from app.repositories.catalog import AttributeOptionRepository, AttributeRepository, ProductTypeRepository
from app.repositories.search_eval import SearchEvalJudgmentRepository, SearchEvalQueryRepository
from app.schemas.search_eval import (
    EvalJudgmentItem,
    EvalMetricItem,
    EvalQueryImportItem,
    EvalSearchRequest,
    EvalSearchResponse,
    EvalSearchResultItem,
)


async def get_query_or_404(db: AsyncSession, query_id: str) -> SearchEvalQuery:
    query = await SearchEvalQueryRepository(db).get(query_id)
    if not query:
        raise NotFoundError("Search eval query not found", translation_key=E.NOT_FOUND)
    return query


async def build_catalog_context(db: AsyncSession) -> str:
    """Compact bilingual catalog summary (types, attributes, option values) for query seeding."""
    product_types = await ProductTypeRepository(db).list_all()
    attributes = await AttributeRepository(db).list_search_affecting()

    lines: list[str] = []
    if product_types:
        lines.append("PRODUCT TYPES: " + ", ".join(f"{t.name_en} ({t.name_ar})" for t in product_types))
    if attributes:
        attr_lines: list[str] = []
        for a in attributes:
            opts = await AttributeOptionRepository(db).list_major_by_attribute(a.id, limit=8)
            sample = ", ".join(f"{o.value_en} ({o.value_ar})" for o in opts[:4])
            attr_lines.append(f"{a.name_en} ({a.name_ar}): {sample or 'any'}")
        lines.append("ATTRIBUTES: " + "; ".join(attr_lines))
    context = "\n".join(lines)
    return context[:8000]


async def generate_queries(
    db: AsyncSession,
    ai_client: AIEngineClient,
    count: int,
    locales: list[str],
    admin_id: str,
    request_id: str,
    redis: AsyncRedis | None = None,
) -> list[SearchEvalQuery]:
    catalog_context = await build_catalog_context(db)
    result = await ai_client.eval_generate_queries(count, locales, catalog_context, request_id=request_id)
    if result is None or result.get("status") != "ok":
        logger.warning("AI Engine eval_generate_queries returned failure: {}", result)
        raise ServiceUnavailableError("AI Engine query generation failed", translation_key=E.AI_ENGINE_ERROR)

    queries_raw = result.get("queries")
    raw_queries = queries_raw if isinstance(queries_raw, list) else []
    repo = SearchEvalQueryRepository(db)
    created: list[SearchEvalQuery] = []
    for raw in raw_queries:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        locale = str(raw.get("locale", "en"))[:5]
        if not text or locale not in ("en", "ar"):
            continue
        if await repo.get_by_text_locale(text, locale):
            continue
        item = SearchEvalQuery(
            id=str(uuid.uuid4()),
            text=text,
            locale=locale,
            source="llm",
            status="pending",
            created_by=admin_id,
        )
        db.add(item)
        created.append(item)
    await db.commit()
    if redis is not None:
        await invalidate_tables(redis, {"search_eval_queries"})
    return created


async def import_queries(
    db: AsyncSession,
    items: list[EvalQueryImportItem],
    admin_id: str,
    redis: AsyncRedis | None = None,
) -> tuple[int, int, int]:
    query_repo = SearchEvalQueryRepository(db)
    judgment_repo = SearchEvalJudgmentRepository(db)
    created = 0
    skipped = 0
    judgments_created = 0
    for item in items:
        text = item.text.strip()
        locale = item.locale[:5]
        query = await query_repo.get_by_text_locale(text, locale)
        if query:
            skipped += 1
        else:
            query = SearchEvalQuery(
                id=str(uuid.uuid4()),
                text=text,
                locale=locale,
                source="seed",
                status="evaluated" if item.relevant_ids else "pending",
                created_by=admin_id,
            )
            db.add(query)
            created += 1
            await db.flush()
        for pid in item.relevant_ids:
            if await judgment_repo.get_by_query_product(query.id, pid):
                continue
            db.add(
                SearchEvalJudgment(
                    id=str(uuid.uuid4()),
                    query_id=query.id,
                    product_id=pid,
                    relevant=True,
                )
            )
            judgments_created += 1
    await db.commit()
    if redis is not None:
        await invalidate_tables(redis, {"search_eval_queries", "search_eval_judgments"})
    return created, skipped, judgments_created


async def list_queries(
    db: AsyncSession,
    locale: str | None,
    source: str | None,
    status: str | None,
    q: str | None,
    skip: int,
    limit: int,
) -> tuple[list[SearchEvalQuery], int]:
    return await SearchEvalQueryRepository(db).list_filtered(locale, source, status, q, skip, limit)


async def update_query(
    db: AsyncSession,
    query_id: str,
    status: str | None,
    rewritten_query: str | None,
    filters: dict[str, Any] | None,
    redis: AsyncRedis | None = None,
) -> SearchEvalQuery:
    query = await get_query_or_404(db, query_id)
    if status is not None:
        query.status = status
    if rewritten_query is not None:
        query.rewritten_query = rewritten_query
    if filters is not None:
        query.filters = filters
    await db.commit()
    await db.refresh(query)
    if redis is not None:
        await invalidate_tables(redis, {"search_eval_queries"})
    return query


async def replace_judgments(db: AsyncSession, query_id: str, judgments: list[EvalJudgmentItem]) -> None:
    judgment_repo = SearchEvalJudgmentRepository(db)
    await judgment_repo.delete_by_query_id(query_id)
    for item in judgments:
        db.add(
            SearchEvalJudgment(
                id=str(uuid.uuid4()),
                query_id=query_id,
                product_id=item.product_id,
                relevant=item.relevant,
                rank=item.rank,
            )
        )


async def save_judgments(db: AsyncSession, query_id: str, judgments: list[EvalJudgmentItem], redis: AsyncRedis | None = None) -> SearchEvalQuery:
    query = await get_query_or_404(db, query_id)
    await replace_judgments(db, query_id, judgments)
    query.status = "evaluated" if any(j.relevant for j in judgments) else query.status
    await db.commit()
    await db.refresh(query)
    if redis is not None:
        await invalidate_tables(redis, {"search_eval_judgments"})
    return query


def _metric_item(locale: str, queries: list[SearchEvalQuery], judgments: list[SearchEvalJudgment]) -> EvalMetricItem:
    by_query: dict[str, list[SearchEvalJudgment]] = {}
    for j in judgments:
        by_query.setdefault(j.query_id, []).append(j)

    query_ids = {q.id for q in queries}
    mrr_total = 0.0
    recall_total = 0.0
    evaluated = 0
    for q in queries:
        qj = [j for j in by_query.get(q.id, []) if j.query_id in query_ids]
        relevant = [j for j in qj if j.relevant]
        if not relevant:
            continue
        evaluated += 1
        best_rank = min((j.rank for j in relevant if j.rank is not None), default=None)
        mrr_total += 1.0 / best_rank if best_rank is not None and best_rank <= 10 else 0.0
        in_top10 = [j for j in relevant if j.rank is not None and j.rank <= 10]
        recall_total += len(in_top10) / len(relevant)

    count = evaluated
    return EvalMetricItem(
        locale=locale,
        query_count=count,
        mrr_10=round(mrr_total / count, 4) if count else 0.0,
        recall_10=round(recall_total / count, 4) if count else 0.0,
    )


async def get_metrics(db: AsyncSession, redis: AsyncRedis | None = None) -> tuple[EvalMetricItem, list[EvalMetricItem]]:
    async def _fetch() -> dict[str, Any]:
        queries = await SearchEvalQueryRepository(db).list_evaluated()
        judgments = await SearchEvalJudgmentRepository(db).list_all()

        per_locale: list[EvalMetricItem] = []
        for locale in ("en", "ar"):
            locale_queries = [q for q in queries if q.locale == locale]
            per_locale.append(_metric_item(locale, locale_queries, judgments))
        overall = _metric_item("all", queries, judgments)
        return {
            "overall": overall.model_dump(mode="json"),
            "per_locale": [item.model_dump(mode="json") for item in per_locale],
        }

    if redis is None:
        result = await _fetch()
    else:
        result = await cache_or_fetch(redis, CacheKeys.search_eval_metrics("all"), CacheKeys.SEARCH_EVAL_METRICS.ttl, _fetch)
    return (
        EvalMetricItem.model_validate(result["overall"]),
        [EvalMetricItem.model_validate(item) for item in result["per_locale"]],
    )


async def eval_search(
    ai_client: AIEngineClient,
    body: EvalSearchRequest,
    request_id: str,
) -> EvalSearchResponse:
    result = await ai_client.eval_search(body.query, body.locale, body.limit, request_id=request_id)
    if result is None or result.get("status") != "ok":
        logger.warning("AI Engine eval_search returned failure: {}", result)
        raise ServiceUnavailableError("AI Engine search failed", translation_key=E.AI_ENGINE_ERROR)

    results_raw = result.get("results")
    raw_results = results_raw if isinstance(results_raw, list) else []
    results: list[EvalSearchResultItem] = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        product = raw.get("product")
        if not isinstance(product, dict):
            continue
        results.append(
            EvalSearchResultItem(
                rank=int(raw.get("rank", 0)),
                score=float(raw.get("score", 0.0)),
                id=str(product.get("id", "")),
                name=product.get("name"),
                price=product.get("price"),
                currency=str(product.get("currency", "SAR")),
                brand=product.get("brand"),
                image_url=normalize_image_url(product.get("image_url")),
                store_id=product.get("store_id"),
                product_data=product.get("product_data") if isinstance(product.get("product_data"), dict) else None,
            )
        )

    rewritten_raw = result.get("rewritten_query")
    filters_raw = result.get("filters")
    specs_raw = result.get("specs")
    return EvalSearchResponse(
        query=body.query,
        locale=body.locale,
        rewritten_query=rewritten_raw if isinstance(rewritten_raw, str) else None,
        filters=filters_raw if isinstance(filters_raw, dict) else None,
        specs=specs_raw if isinstance(specs_raw, list) else [],
        results=results,
    )
