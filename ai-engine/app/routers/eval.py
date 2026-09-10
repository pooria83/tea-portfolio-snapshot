from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.core.logging import request_id_var, user_id_var
from app.routers.chat import (
    _resolve_search,
    augment_query_text,
    build_messages,
    get_comm_llm,
    get_embedder,
    get_llm,
    get_rag,
)
from app.schemas.chat import ChatRequest, ProductRef, SearchSpec
from app.schemas.eval import (
    EvalQueriesRequest,
    EvalQueriesResponse,
    EvalQueryItem,
    EvalSearchRequest,
    EvalSearchResponse,
    EvalSearchResult,
)
from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient
from app.services.rag import RAGService

router = APIRouter(prefix="/eval", tags=["eval"])


async def _run_search_scored(
    embedder: EmbeddingClient,
    rag: RAGService,
    specs: list[tuple[str, dict[str, list[str]] | None]],
    limit: int,
    prefer_lang: str | None = None,
) -> list[tuple[ProductRef, float]]:
    """Run every search spec and merge scored results, deduping by product id."""
    merged: list[tuple[ProductRef, float]] = []
    seen: set[str] = set()
    for search_query, filters in specs:
        query_text = augment_query_text(search_query, filters)
        try:
            query_vec = await embedder.embed_query(query_text)
        except Exception:
            logger.exception("EMBED_EXCEPTION search_query={}", search_query)
            query_vec = None
        if query_vec is None:
            logger.error("EMBED_FAILED search_query={}", search_query)
            raise HTTPException(status_code=502, detail="Embedding failed")
        scored = await rag.search_scored(
            query_vec,
            limit=limit,
            filters=filters,
            query_text=query_text,
            prefer_lang=prefer_lang,
        )
        for product, score in scored:
            if product.id not in seen:
                seen.add(product.id)
                merged.append((product, score))
    return merged


@router.post("/queries", response_model=EvalQueriesResponse)
async def eval_queries(
    body: EvalQueriesRequest,
    comm_llm: LLMClient = Depends(get_comm_llm),
) -> EvalQueriesResponse:
    logger.info(
        "EVAL_QUERIES_START request_id={} user_id={} count={} locales={}",
        request_id_var.get(),
        user_id_var.get(),
        body.count,
        body.locales,
    )
    queries = await comm_llm.generate_eval_queries(
        body.count,
        body.locales,
        body.catalog_context,
    )
    if queries is None:
        logger.error("EVAL_QUERIES_FAILED count={}", body.count)
        raise HTTPException(status_code=502, detail="Query generation failed")
    logger.info("EVAL_QUERIES_DONE count={} generated={}", body.count, len(queries))
    return EvalQueriesResponse(queries=[EvalQueryItem(**q) for q in queries])


@router.post("/search", response_model=EvalSearchResponse)
async def eval_search(
    body: EvalSearchRequest,
    llm: LLMClient = Depends(get_llm),
    comm_llm: LLMClient = Depends(get_comm_llm),
    embedder: EmbeddingClient = Depends(get_embedder),
    rag: RAGService = Depends(get_rag),
) -> EvalSearchResponse:
    logger.info(
        "EVAL_SEARCH_START request_id={} user_id={} query={} locale={} limit={}",
        request_id_var.get(),
        user_id_var.get(),
        body.query,
        body.locale,
        body.limit,
    )
    chat_request = ChatRequest(query=body.query, locale=body.locale, limit=body.limit)
    messages = build_messages(body.query, [], "")
    specs, tool_used, debug, direct_answer = await _resolve_search(
        comm_llm,
        llm,
        chat_request,
        messages,
        use_tools=False,
    )
    logger.info("EVAL_SEARCH_RESOLVED query={} specs={} tool_used={}", body.query, len(specs), tool_used)
    if direct_answer or not specs:
        logger.info("EVAL_SEARCH_NO_SPECS query={}", body.query)
        return EvalSearchResponse(
            query=body.query,
            locale=body.locale,
            rewritten_query=None,
            filters=None,
            specs=[],
            results=[],
        )

    scored = await _run_search_scored(embedder, rag, specs, body.limit, prefer_lang=body.locale)
    results = [EvalSearchResult(rank=rank, score=score, product=product) for rank, (product, score) in enumerate(scored, start=1)]
    logger.info("EVAL_SEARCH_DONE query={} results={}", body.query, len(results))
    return EvalSearchResponse(
        query=body.query,
        locale=body.locale,
        rewritten_query=specs[0][0],
        filters=specs[0][1],
        specs=[SearchSpec(query=query, filters=filters) for query, filters in specs],
        results=results,
    )
