import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.core.logging import request_id_var, user_id_var
from app.schemas.chat import ChatDebug, ChatRequest, ChatResponse, ProductRef, SearchContext, SearchSpec
from app.services.embedding_client import EmbeddingClient
from app.services.lang_detect import detect_locale
from app.services.llm_client import LLMClient
from app.services.prompts import CHAT_SYSTEM_PROMPT
from app.services.rag import RAGService, _tokenize
from app.services.search_tools import SEARCH_PRODUCTS_TOOL, inject_color_filter, normalize_filters, normalize_tool_args

router = APIRouter(tags=["chat"])

_NO_RESULTS_HINTS = {
    "ar": "لم أجد منتجات مطابقة. جرّب بحثاً مختلفاً.",
    "fa": "محصولی مطابق پیدا نکردم. لطفاً جستجوی دیگری را امتحان کنید.",
    "en": "I couldn't find any matching products. Try a different search.",
}


def _sse(frame: dict[str, Any]) -> str:
    """Serialize one SSE frame as a single newline-terminated JSON line."""
    return json.dumps(frame) + "\n"


def _no_results_text(locale: str) -> str:
    return _NO_RESULTS_HINTS.get(locale, _NO_RESULTS_HINTS["en"])


# Filter keys whose values add no semantic signal to the embedded query text
# (size numbers / "one size" are exact-match filters, not lexical terms).
_FILTER_KEYS_SKIPPED_IN_QUERY = {"_size", "size"}


def augment_query_text(query: str, filters: dict[str, list[str]] | None) -> str:
    """Append filter values to the query text used for dense+sparse embedding.

    The vector query then aligns with the filtered subspace — e.g. a red-dress
    filter contributes ``pink`` tokens the LLM may have dropped from the
    rewritten query (search quality plan item 3). Comparison is at stemmed
    token level (the sparse tokenizer), so case variants (``Watches`` /
    ``WATCHES``) and already-present words add nothing; only genuinely new
    stemmed tokens are appended. Size filters are skipped: numbers and "one
    size" add no semantic signal. Query-side only — display text is untouched.
    """
    if not filters:
        return query
    query_tokens = set(_tokenize(query))
    parts = [query]
    for key, values in filters.items():
        if key.lower() in _FILTER_KEYS_SKIPPED_IN_QUERY:
            continue
        for value in values:
            v = str(value).strip()
            if not v:
                continue
            new_tokens = [t for t in _tokenize(v) if t not in query_tokens]
            if not new_tokens:
                continue
            parts.append(" ".join(new_tokens))
            query_tokens.update(new_tokens)
    return " ".join(parts)


async def get_llm(request: Request) -> LLMClient:
    return cast(LLMClient, request.app.state.llm_client)


async def get_comm_llm(request: Request) -> LLMClient:
    return cast(LLMClient, request.app.state.comm_llm_client)


async def get_embedder(request: Request) -> EmbeddingClient:
    return cast(EmbeddingClient, request.app.state.embedding_client)


async def get_rag(request: Request) -> RAGService:
    return cast(RAGService, request.app.state.rag_service)


def build_messages(
    query: str,
    history: list[dict[str, str]],
    summary: str,
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt or CHAT_SYSTEM_PROMPT}]
    if summary:
        messages.append({"role": "system", "content": f"Previous conversation summary:\n{summary}"})
    messages.extend(history)
    messages.append({"role": "user", "content": query})
    return messages


async def _run_search(
    embedder: EmbeddingClient,
    rag: RAGService,
    search_query: str,
    filters: dict[str, list[str]] | None,
    limit: int,
    prefer_lang: str | None = None,
) -> list[ProductRef]:
    query_text = augment_query_text(search_query, filters)
    try:
        query_vec = await embedder.embed_query(query_text)
    except Exception:
        logger.exception("EMBED_EXCEPTION search_query={}", search_query)
        query_vec = None
    if query_vec is None:
        logger.error("EMBED_FAILED search_query={}", search_query)
        raise HTTPException(status_code=502, detail="Embedding failed")
    logger.info("EMBED_DONE search_query={} query_text={!r} vector_dim={}", search_query, query_text, len(query_vec))
    products = await rag.search(query_vec, limit=limit, filters=filters, query_text=query_text, prefer_lang=prefer_lang)
    logger.info("SEARCH_RESULTS count={} filters={}", len(products), filters)
    return products


async def _run_search_specs(
    embedder: EmbeddingClient,
    rag: RAGService,
    specs: list[tuple[str, dict[str, list[str]] | None]],
    limit: int,
    prefer_lang: str | None = None,
) -> list[ProductRef]:
    """Run every search spec and merge results, deduplicating by product id."""
    merged: list[ProductRef] = []
    seen: set[str] = set()
    for search_query, filters in specs:
        products = await _run_search(embedder, rag, search_query, filters, limit, prefer_lang)
        for product in products:
            if product.id not in seen:
                seen.add(product.id)
                merged.append(product)
    if len(specs) > 1:
        logger.info("SEARCH_MERGED specs={} total={}", len(specs), len(merged))
    return merged


def _product_payload(products: list[ProductRef]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    payload: list[dict[str, Any]] = []
    for p in products:
        if p.id in seen:
            continue
        seen.add(p.id)
        payload.append(
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "currency": p.currency,
                "brand": p.brand,
                "image_url": p.image_url,
                "store_id": p.store_id,
            }
        )
    return payload


async def _resolve_search(
    comm_llm: LLMClient,
    llm: LLMClient,
    request: ChatRequest,
    messages: list[dict[str, str]],
    use_tools: bool = True,
) -> tuple[list[tuple[str, dict[str, list[str]] | None]], bool, dict[str, Any] | None, str | None]:
    """Tool-calling first, parse-fallback second. Returns (search_specs, tool_used, debug, direct_answer).

    Each spec is (search_query, filters). Multiple parallel tool calls yield
    multiple specs — every spec is executed and results are merged.
    When the model answers without calling the tool, `direct_answer` is the
    response and no search should run. When ``use_tools`` is False (eval path)
    the parse path runs directly — deterministic, no tool-calling variance.
    """
    tool_used = False
    debug: dict[str, Any] | None = None
    if use_tools:
        search_messages = [m for m in messages if m["role"] != "assistant"]
        try:
            tool_result = await comm_llm.chat_with_tools(search_messages, tools=[SEARCH_PRODUCTS_TOOL], locale=request.locale, capture_debug=True)
            debug = _valid_debug_dict(comm_llm.take_captured_debug())
        except Exception:
            logger.warning("TOOL_CALL_UNSUPPORTED — falling back to parse path")
            tool_result = None
        if tool_result is not None and tool_result.tool_call_args:
            specs: list[tuple[str, dict[str, list[str]] | None]] = []
            for args in tool_result.tool_call_args:
                tool_search_query, tool_filters = normalize_tool_args(args)
                if not tool_search_query:
                    tool_search_query = request.query
                tool_filters = inject_color_filter(tool_search_query, tool_filters)
                specs.append((tool_search_query, tool_filters))
            tool_used = True
            logger.info("TOOL_SEARCH specs={}", specs)
            return (specs, tool_used, debug, None)

        if tool_result is not None and tool_result.answer:
            logger.info("TOOL_DIRECT_ANSWER — model answered without searching, answer={}", tool_result.answer[:200])
            return ([], False, debug, tool_result.answer)

    parsed = await llm.parse_search_query(request.query, locale=request.locale, capture_debug=True, prompt=request.parse_prompt)
    debug = _valid_debug_dict(llm.take_captured_debug())
    search_query = request.query
    filters: dict[str, list[str]] | None = None
    if parsed:
        rewritten = cast("str | None", parsed.get("rewritten_query"))
        if rewritten and rewritten.strip():
            search_query = rewritten.strip()
        raw_filters = cast("dict[str, object] | None", parsed.get("filters"))
        filters = normalize_filters(raw_filters)
        filters = inject_color_filter(search_query, filters)
        logger.info("LLM_PARSE original={} rewritten={} filters={}", request.query, search_query, filters)
    else:
        logger.info("LLM_PARSE failed or no result — using raw query as-is")

    specs = [(search_query, filters)]
    # Dual-spec safety net: when the rewrite changed the query, also search the
    # raw query verbatim so attribute/feature words the LLM dropped from the
    # rewrite (neckline, sleeve, movement type, fragrance notes, ...) still
    # reach the vector search — they are matched by embedding, not filters.
    if search_query != request.query:
        raw_spec_filters = inject_color_filter(request.query, dict(filters) if filters else None)
        specs.append((request.query, raw_spec_filters))
    return (specs, tool_used, debug, None)


def _search_context(specs: list[tuple[str, dict[str, list[str]] | None]], tool_used: bool, intent: str = "search") -> SearchContext:
    """SearchContext surfaces every executed spec; the first spec stays in the
    legacy rewritten_query/filters fields for backward compatibility."""
    return SearchContext(
        rewritten_query=specs[0][0] if specs else None,
        filters=specs[0][1] if specs else None,
        tool_used=tool_used,
        specs=[SearchSpec(query=query, filters=filters) for query, filters in specs],
        intent=cast("Any", intent),
    )


def _as_chat_debug(debug: Any) -> ChatDebug | None:
    if isinstance(debug, dict) and debug.get("prompt") is not None and debug.get("response") is not None:
        return ChatDebug(prompt=debug["prompt"], response=debug["response"])
    return None


def _valid_debug_dict(debug: Any) -> dict[str, Any] | None:
    if isinstance(debug, dict) and debug.get("prompt") is not None and debug.get("response") is not None:
        return cast("dict[str, Any]", debug)
    return None


@router.post("/chat", response_model=None)
async def chat(
    request: ChatRequest,
    llm: LLMClient = Depends(get_llm),
    comm_llm: LLMClient = Depends(get_comm_llm),
    embedder: EmbeddingClient = Depends(get_embedder),
    rag: RAGService = Depends(get_rag),
) -> ChatResponse | StreamingResponse:
    logger.info("=== CHAT START === user_query={} locale={} limit={} history={}", request.query, request.locale, request.limit, len(request.history))

    # Pre-flight probes are advisory: a failed ping (transient network blip,
    # cold tunnel) only warns. The real embed/LLM calls below carry 60s
    # timeouts and are the arbiter — they raise 502 / emit an SSE error frame
    # if the endpoint is actually unreachable.
    embedder_ok, llm_ok = await asyncio.gather(embedder.health(), comm_llm.health())
    if not embedder_ok:
        logger.warning("PREFLIGHT_EMBEDDER_DOWN — proceeding anyway; the real embed call is the arbiter")
    if not llm_ok:
        logger.warning("PREFLIGHT_LLM_DOWN — proceeding anyway; the real LLM call is the arbiter")

    logger.info(
        "TRACE_CHAT_START request_id={} user_id={} query={} locale={} history={} summary_len={} stream={}",
        request_id_var.get(),
        user_id_var.get(),
        request.query,
        request.locale,
        len(request.history),
        len(request.summary),
        request.stream,
    )

    effective_locale = detect_locale(request.query) or request.locale
    messages = build_messages(
        request.query,
        [{"role": h.role, "content": h.content} for h in request.history],
        request.summary,
        system_prompt=request.system_prompt,
    )

    intent = await comm_llm.classify_intent(request.query, [{"role": h.role, "content": h.content} for h in request.history], locale=request.locale)
    logger.info("ROUTER_INTENT query={} intent={}", request.query, intent)
    logger.info("TRACE_CHAT intent={} query={}", intent, request.query)

    if intent == "greeting":
        logger.info("ROUTER_GREETING — returning friendly reply without search")
        logger.info("TRACE_CHAT type=greeting")
        return await _plain_answer(request, comm_llm, messages, "greeting")

    if intent == "general":
        logger.info("ROUTER_GENERAL — returning plain LLM answer without search")
        logger.info("TRACE_CHAT type=general")
        return await _plain_answer(request, comm_llm, messages, "general")

    search_specs, tool_used, debug, direct_answer = await _resolve_search(comm_llm, llm, request, messages)
    logger.info("TRACE_CHAT type=search specs={} tool_used={} direct={}", len(search_specs), tool_used, bool(direct_answer))

    if direct_answer:
        logger.info("DIRECT_ANSWER — returning model answer without search")
        if request.stream:
            return StreamingResponse(
                _stream_direct_answer(request, direct_answer, _search_context([], False, intent="search"), debug),
                media_type="text/event-stream",
            )
        logger.info("TRACE_CHAT_END type=search products=0 answer_len={}", len(direct_answer))
        return ChatResponse(
            answer=direct_answer,
            products=[],
            search_context=_search_context([], False, intent="search"),
            debug=_as_chat_debug(debug),
        )

    if request.stream:
        logger.info("TRACE_CHAT_STREAM type=search specs={}", len(search_specs))
        return StreamingResponse(
            _stream_chat(request, comm_llm, embedder, rag, messages, search_specs, tool_used, debug),
            media_type="text/event-stream",
        )

    products = await _run_search_specs(embedder, rag, search_specs, request.limit, effective_locale)
    if not products:
        logger.info("SEARCH_ZERO_RESULTS specs={}", search_specs)
        no_results = _no_results_text(effective_locale)
        logger.info("TRACE_CHAT_END type=search products=0 answer_len={}", len(no_results))
        return ChatResponse(
            answer=no_results,
            products=[],
            search_context=_search_context(search_specs, tool_used),
            debug=_as_chat_debug(debug),
        )

    context = rag.format_products_for_prompt(products, locale=effective_locale)
    answer = await comm_llm.chat_with_context(messages, context, locale=request.locale)
    if answer is None:
        logger.error("LLM_RESPONSE_FAILED user_query={}", request.query)
        raise HTTPException(status_code=502, detail="Chat generation failed")

    logger.info("=== CHAT END ===")
    logger.info("TRACE_CHAT_END type=search products={} answer_len={}", len(products), len(answer))
    return ChatResponse(
        answer=answer,
        products=products,
        search_context=_search_context(search_specs, tool_used),
        debug=_as_chat_debug(debug),
    )


async def _plain_answer(
    request: ChatRequest,
    comm_llm: LLMClient,
    messages: list[dict[str, str]],
    intent: str,
) -> ChatResponse | StreamingResponse:
    """Greeting/general branch: plain LLM answer, no search, no products."""
    search_context = _search_context([], False, intent=intent)
    if request.stream:
        logger.info("TRACE_CHAT_STREAM type={}", intent)
        return StreamingResponse(
            _stream_plain(request, comm_llm, messages, search_context),
            media_type="text/event-stream",
        )
    answer = await comm_llm.chat_plain(messages, locale=request.locale)
    if answer is None:
        logger.error("PLAIN_CHAT_FAILED intent={} user_query={}", intent, request.query)
        raise HTTPException(status_code=502, detail="Chat generation failed")
    logger.info("TRACE_CHAT_END type={} products=0 answer_len={}", intent, len(answer))
    return ChatResponse(answer=answer, products=[], search_context=search_context)


async def _stream_plain(
    request: ChatRequest,
    comm_llm: LLMClient,
    messages: list[dict[str, str]],
    search_context: SearchContext,
) -> AsyncGenerator[str, None]:
    """SSE for greeting/general: assistant_start → empty cards → text_chunk* → assistant_end."""
    yield _sse({"type": "assistant_start", "search_context": search_context.model_dump()})
    yield _sse({"type": "product_cards", "products": [], "locale": detect_locale(request.query) or request.locale})
    answer = ""
    try:
        async for delta in comm_llm.chat_plain_stream(messages, locale=request.locale):
            answer += delta
            yield _sse({"type": "text_chunk", "delta": delta})
    except Exception:
        logger.exception("PLAIN_STREAM_FAILED — falling back to non-streaming answer")
        answer = ""
    if not answer:
        try:
            answer = (await comm_llm.chat_plain(messages, locale=request.locale)) or ""
            if answer:
                yield _sse({"type": "text_chunk", "delta": answer})
        except Exception:
            logger.exception("PLAIN_CHAT_FAILED")
            yield _sse({"type": "error", "code": "chat_failed"})
            return
    yield _sse({"type": "assistant_end"})


async def _stream_direct_answer(
    request: ChatRequest,
    answer: str,
    search_context: SearchContext,
    debug: dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    """SSE for the direct-answer path (model answered without searching).

    The answer is already fully generated, so it is emitted as a single
    text_chunk frame.
    """
    if debug:
        yield _sse({"type": "debug", "debug": debug})
    yield _sse({"type": "assistant_start", "search_context": search_context.model_dump()})
    yield _sse({"type": "product_cards", "products": [], "locale": detect_locale(request.query) or request.locale})
    if answer:
        yield _sse({"type": "text_chunk", "delta": answer})
    yield _sse({"type": "assistant_end"})


async def _stream_chat(
    request: ChatRequest,
    comm_llm: LLMClient,
    embedder: EmbeddingClient,
    rag: RAGService,
    messages: list[dict[str, str]],
    search_specs: list[tuple[str, dict[str, list[str]] | None]],
    tool_used: bool,
    debug: dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    if debug:
        yield _sse({"type": "debug", "debug": debug})
    effective_locale = detect_locale(request.query) or request.locale
    try:
        products = await _run_search_specs(embedder, rag, search_specs, request.limit, effective_locale)
    except HTTPException:
        yield _sse({"type": "error", "code": "embedding_failed"})
        return

    yield _sse({"type": "assistant_start", "search_context": _search_context(search_specs, tool_used).model_dump()})
    if not products:
        yield _sse({"type": "product_cards", "products": [], "locale": effective_locale})
        yield _sse({"type": "text_chunk", "delta": _no_results_text(effective_locale)})
        yield _sse({"type": "assistant_end"})
        return
    yield _sse({"type": "product_cards", "products": _product_payload(products), "locale": effective_locale})

    context = rag.format_products_for_prompt(products, locale=effective_locale)
    # Restate the query right before the product context so the model's last
    # user turn still carries the original request.
    stream_messages = messages + [{"role": "user", "content": f"{request.query}\n\nAvailable products:\n{context}"}]
    answer = ""
    try:
        async for delta in comm_llm.chat_stream(stream_messages, locale=request.locale):
            answer += delta
            yield _sse({"type": "text_chunk", "delta": delta})
    except Exception:
        logger.exception("STREAM_FAILED — falling back to non-streaming answer")
        answer = ""
    if not answer:
        try:
            answer = (await comm_llm.chat_with_context(messages, context, locale=request.locale)) or ""
            if answer:
                yield _sse({"type": "text_chunk", "delta": answer})
        except Exception:
            logger.exception("LLM_RESPONSE_FAILED")
            yield _sse({"type": "error", "code": "chat_failed"})
            return
    yield _sse({"type": "assistant_end"})
