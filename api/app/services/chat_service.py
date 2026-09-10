"""Chat history orchestration: conversation lifecycle, engine calls, persistence."""

import json
from collections.abc import AsyncIterator
from typing import Any, cast

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIEngineClient
from app.core.config import settings
from app.core.error_codes import E
from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.images import normalize_image_url
from app.core.lang_detect import detect_locale
from app.repositories.catalog import CategoryRepository
from app.repositories.conversation_repo import ConversationRepo
from app.repositories.llm import LLMModelRepository, LLMSettingRepository
from app.repositories.message_repo import MessageRepo
from app.repositories.product_definition import StoreProductRepository
from app.repositories.settings import PromptTemplateRepository
from app.schemas.chat import message_from_doc
from app.services.prompt_defaults import CHAT_ASSISTANT, PARSE_QUERY, SUMMARIZE, TITLE

_DEFAULT_CONTEXT_BUDGET = 12000

_SIMILAR_LABELS = {
    "en": "👆👆 Here are similar products to {name}",
    "ar": "👆👆 هذه منتجات مشابهة لـ {name}",
    "fa": "👆👆 این محصولات مشابه {name} هستند",
}


def _similar_label(locale: str, product_name: str) -> str:
    template = _SIMILAR_LABELS.get(locale, _SIMILAR_LABELS["en"])
    return template.format(name=product_name or "")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _snapshot_from_product(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(p.get("id", "")),
        "name": p.get("name"),
        "name_ar": p.get("name_ar"),
        "name_en": p.get("name_en"),
        "name_fa": p.get("name_fa"),
        "price": p.get("price"),
        "currency": p.get("currency", "SAR"),
        "brand": p.get("brand"),
        "brand_ar": p.get("brand_ar"),
        "brand_en": p.get("brand_en"),
        "brand_fa": p.get("brand_fa"),
        "image_url": normalize_image_url(p.get("image_url")),
        "buy_url": p.get("buy_url"),
        "store_id": p.get("store_id"),
    }


class ChatService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase[dict[str, Any]],
        ai_client: AIEngineClient,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        redis: AsyncRedis | None = None,
    ) -> None:
        self.conversations = ConversationRepo(db)
        self.messages = MessageRepo(db)
        self.ai_client = ai_client
        self.session_factory = session_factory
        self.redis = redis

    async def ensure_active_conversation(self, user_id: str, locale: str, app_version: str = "", need_title: bool = True) -> dict[str, Any]:
        existing = await self.conversations.find_active_by_user(user_id)
        if existing:
            return existing
        return await self.conversations.create(user_id, locale, app_version, need_title=need_title)

    async def claim_turn(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
        idempotency_key: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any], str, list[dict[str, object]], str]:
        """Claim a message slot and persist the user message.

        Returns (conversation, user_message, summary, history, locale).
        """
        conversation = None
        if idempotency_key:
            existing_message = await self.messages.find_by_idempotency_key(idempotency_key)
            if existing_message is not None:
                conversation = await self.conversations.find_by_id_and_user(conversation_id, user_id)
                if conversation is None:
                    raise NotFoundError("Conversation not found", translation_key=E.CONVERSATION_NOT_FOUND)
                summary = str(conversation.get("summary", ""))
                locale = str(conversation.get("locale", "en"))
                messages = await self.messages.list_all_before(conversation_id)
                history = await self._build_history(messages)
                return conversation, existing_message, summary, history, locale

        conversation = await self.conversations.claim_message_slot(conversation_id, user_id)
        if conversation is None:
            doc = await self.conversations.find_by_id_and_user(conversation_id, user_id)
            if doc is None:
                raise NotFoundError("Conversation not found", translation_key=E.CONVERSATION_NOT_FOUND)
            if doc["userMessageCount"] >= settings.chat_max_messages:
                raise ConflictError("Message limit reached", translation_key=E.CHAT_LIMIT_REACHED)
            raise ConflictError("Conversation is closed", translation_key=E.CONVERSATION_CLOSED)

        summary = str(conversation.get("summary", ""))
        locale = str(conversation.get("locale", "en"))
        detected = detect_locale(content)
        if detected is not None and detected != locale:
            locale = detected
            try:
                await self.conversations.update_locale(conversation_id, detected)
            except Exception:
                logger.opt(exception=True).warning("locale_update_failed conversation_id={}", conversation_id)
        messages = await self.messages.list_all_before(conversation_id)
        history = await self._build_history(messages)
        user_message = await self.messages.create(
            conversation_id,
            "user",
            content,
            token_count=_estimate_tokens(content),
            idempotency_key=idempotency_key,
        )
        return conversation, user_message, summary, history, locale

    async def _active_prompt(self, type_: str) -> str | None:
        """Active prompt content from the prompt_templates table.

        Returns None when the Postgres session is unavailable or no active row
        exists — callers then let the engine use its own defaults.
        """
        if self.session_factory is None:
            return None
        try:
            async with self.session_factory() as session:
                return await PromptTemplateRepository(session, self.redis).get_active_content(type_)
        except Exception:
            logger.opt(exception=True).warning("prompt_fetch_failed type={}", type_)
            return None

    async def chat_prompts(self) -> tuple[str | None, str | None]:
        """(system_prompt, parse_prompt) for the chat flow; None = engine default."""
        return (
            await self._active_prompt(CHAT_ASSISTANT),
            await self._active_prompt(PARSE_QUERY),
        )

    async def enrich_product_names(self, products: list[dict[str, Any]]) -> None:
        """Attach trilingual name/brand fields to product cards from PostgreSQL.

        The engine only carries the English display name; localized names live
        in store_products/brands. Already-enriched cards are skipped (single
        batched lookup per turn). Failures are logged, never propagated — cards
        keep their English names when the lookup is unavailable.
        """
        if not products or self.session_factory is None:
            return
        ids = [str(p.get("id", "")) for p in products if p.get("id") and not p.get("name_ar")]
        if not ids:
            return
        try:
            async with self.session_factory() as session:
                rows = await StoreProductRepository(session).list_names_brands(ids)
        except Exception:
            logger.opt(exception=True).warning("product_name_enrichment_failed ids={}", ids)
            return
        by_id = {str(row[0]): row for row in rows}
        for p in products:
            row = by_id.get(str(p.get("id", "")))
            if row is None:
                continue
            for key, value in (("name_ar", row[1]), ("name_en", row[2]), ("name_fa", row[3]), ("brand_ar", row[4]), ("brand_en", row[5]), ("brand_fa", row[6])):
                if value:
                    p[key] = value

    async def persist_assistant(
        self,
        conversation_id: str,
        content: str,
        products: list[dict[str, Any]],
        search_context: dict[str, Any] | None = None,
        token_count: int | None = None,
        debug: dict[str, Any] | None = None,
        locale: str = "",
    ) -> dict[str, Any]:
        await self.enrich_product_names(products)
        return await self.messages.create(
            conversation_id,
            "assistant",
            content,
            token_count=token_count or _estimate_tokens(content),
            product_snapshots=[_snapshot_from_product(p) for p in products],
            search_context=search_context,
            debug=debug,
            locale=locale or None,
        )

    async def persist_failed(
        self,
        conversation_id: str,
        error: str,
        search_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.messages.create(
            conversation_id,
            "assistant",
            "",
            status="failed",
            error=error,
            search_context=search_context,
        )

    async def _similar_category_chain(self, product_id: str) -> list[list[str]] | None:
        """Bilingual category chain (leaf -> parent -> ... -> root) for the AI
        Engine's hierarchical same-category filter. Returns None when the
        session factory is unavailable or the lookup fails (falls back to
        unfiltered vector search)."""
        if self.session_factory is None:
            return None
        try:
            async with self.session_factory() as db:
                category_id = await StoreProductRepository(db).get_category_id(product_id)
                if category_id is None:
                    return None
                chain: list[list[str]] = []
                for node in await CategoryRepository(db).get_chain(category_id):
                    names = [str(node[1] or ""), str(node[2] or "")]
                    if any(names):
                        chain.append(names)
                return chain or None
        except Exception:
            logger.warning("similar_category_chain_failed product_id={}", product_id, exc_info=True)
            return None

    async def find_similar(
        self,
        conversation_id: str,
        user_id: str,
        product_id: str,
        request_id: str = "",
        product_name: str = "",
    ) -> dict[str, Any]:
        """Find products similar to an already-indexed product and persist the
        result as an assistant message. Consumes no user message slot."""
        conversation = await self.conversations.find_by_id_and_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation not found", translation_key=E.CONVERSATION_NOT_FOUND)
        if conversation.get("status") != "active":
            raise ConflictError("Conversation is closed", translation_key=E.CONVERSATION_CLOSED)
        locale = str(conversation.get("locale", "en"))
        try:
            categories = await self._similar_category_chain(product_id)
            result = await self.ai_client.similar_products(
                product_id=product_id,
                locale=locale,
                request_id=request_id,
                user_id=user_id,
                categories=categories,
            )
        except NotFoundError:
            raise
        except Exception:
            logger.exception("similar_engine_failed user_id={} conversation_id={} product_id={}", user_id, conversation_id, product_id)
            raise ServiceUnavailableError("Similar products failed", translation_key=E.CHAT_ENGINE_FAILED) from None
        products = cast("list[dict[str, Any]]", result.get("products", []))
        if not isinstance(products, list):
            products = []
        for p in products:
            url = p.get("image_url")
            if isinstance(url, str):
                p["image_url"] = normalize_image_url(url)
        label = _similar_label(locale, product_name)
        return await self.persist_assistant(conversation_id, label, products, locale=locale)

    async def send_message(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
        idempotency_key: str = "",
        request_id: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Persist the user turn, call the engine with history + summary, persist the answer."""
        conversation, user_message, summary, history, locale = await self.claim_turn(user_id, conversation_id, content, idempotency_key)

        try:
            system_prompt, parse_prompt = await self.chat_prompts()
            result = await self.ai_client.chat_conversational(
                query=content,
                locale=locale,
                history=history,
                summary=summary,
                system_prompt=system_prompt,
                parse_prompt=parse_prompt,
                request_id=request_id,
                user_id=user_id,
            )
        except Exception:
            logger.exception("chat_engine_failed user_id={} conversation_id={}", user_id, conversation_id)
            await self.persist_failed(conversation_id, "chat_engine_failed")
            raise ServiceUnavailableError("Chat generation failed", translation_key=E.CHAT_ENGINE_FAILED) from None

        answer = str(result.get("answer", ""))
        products_data = cast("list[dict[str, Any]]", result.get("products", []))
        search_context = result.get("search_context")
        debug = result.get("debug")
        assistant_message = await self.persist_assistant(
            conversation_id,
            answer,
            products_data if isinstance(products_data, list) else [],
            search_context=dict(search_context) if isinstance(search_context, dict) else None,
            debug=dict(debug) if isinstance(debug, dict) else None,
            locale=locale,
        )
        await self.maybe_compact(conversation_id)
        await self.maybe_title(conversation_id, content, locale)
        return conversation, user_message, assistant_message

    async def send_message_stream(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
        idempotency_key: str = "",
        request_id: str = "",
        include_saved_message: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a chat turn as engine frames, persisting on completion.

        Yields each engine frame (text_chunk/product_cards/assistant_start/
        debug/...) for the caller to relay, finishing with a synthetic
        ``{"type": "message_saved", "message_id": ..., "message": ...,
        "user_message": ...}`` frame carrying the persisted assistant and user
        messages. Raises NotFoundError/ConflictError when the turn cannot be
        claimed. Engine failures are persisted as a failed message and reported
        via an ``error`` frame before ``message_saved`` — the stream never
        raises after the turn is claimed.
        """
        _conversation, user_message, summary, history, locale = await self.claim_turn(user_id, conversation_id, content, idempotency_key)

        deltas: list[str] = []
        products: list[dict[str, Any]] = []
        search_context: dict[str, Any] | None = None
        debug: dict[str, Any] | None = None
        saved: dict[str, Any] | None = None
        stream_failed = False
        error_code: str | None = None
        try:
            system_prompt, parse_prompt = await self.chat_prompts()
            try:
                async for line in self.ai_client.chat_conversational_stream(
                    query=content,
                    locale=locale,
                    history=history,
                    summary=summary,
                    system_prompt=system_prompt,
                    parse_prompt=parse_prompt,
                    request_id=request_id,
                    user_id=user_id,
                ):
                    try:
                        frame = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(frame, dict):
                        continue
                    frame_type = frame.get("type")
                    if frame_type == "text_chunk":
                        delta = str(frame.get("delta", ""))
                        if delta:
                            deltas.append(delta)
                    elif frame_type == "product_cards":
                        cards = frame.get("products")
                        if isinstance(cards, list):
                            products = [p for p in cards if isinstance(p, dict)]
                            await self.enrich_product_names(products)
                            for p in products:
                                url = p.get("image_url")
                                if isinstance(url, str):
                                    p["image_url"] = normalize_image_url(url)
                            frame["products"] = products
                    elif frame_type == "assistant_start":
                        sc = frame.get("search_context")
                        search_context = dict(sc) if isinstance(sc, dict) else None
                    elif frame_type == "debug":
                        dbg = frame.get("debug")
                        debug = dict(dbg) if isinstance(dbg, dict) else None
                    elif frame_type == "error":
                        code = frame.get("code")
                        if isinstance(code, str) and code:
                            error_code = code
                    yield frame
            except Exception:
                stream_failed = True
                logger.exception("chat_stream_engine_failed user_id={} conversation_id={}", user_id, conversation_id)
        finally:
            try:
                answer = "".join(deltas).strip()
                if answer or products:
                    saved = await self.persist_assistant(
                        conversation_id,
                        answer,
                        products,
                        search_context=search_context,
                        debug=debug,
                        locale=locale,
                    )
                else:
                    code = error_code or ("chat_failed" if stream_failed else "chat_engine_failed")
                    saved = await self.persist_failed(
                        conversation_id,
                        code,
                        search_context={"intent": "error"},
                    )
            except Exception:
                logger.exception("chat_stream_persist_failed conversation_id={}", conversation_id)
            await self.maybe_compact(conversation_id)
            await self.maybe_title(conversation_id, content, locale)
        if stream_failed:
            yield {"type": "error", "code": "chat_failed"}
        saved_frame: dict[str, Any] = {
            "type": "message_saved",
            "conversation_id": conversation_id,
            "message_id": str(saved.get("_id", "")) if saved else None,
        }
        if include_saved_message:
            if saved:
                saved_frame["message"] = message_from_doc(saved).model_dump(mode="json")
            if user_message:
                saved_frame["user_message"] = message_from_doc(user_message).model_dump(mode="json")
        yield saved_frame

    async def _build_history(self, messages: list[dict[str, Any]]) -> list[dict[str, object]]:
        """Last messages for context: capped by count and by token budget."""
        messages = messages[-settings.chat_history_window :]
        budget = await self._context_budget()
        history: list[dict[str, object]] = []
        used = 0
        for m in messages:
            if m["role"] not in ("user", "assistant") or not m.get("content"):
                continue
            content = str(m["content"])
            cost = int(m.get("tokenCount") or _estimate_tokens(content))
            if history and used + cost > budget:
                break
            history.append({"role": m["role"], "content": content})
            used += cost
        return history

    async def _context_budget(self) -> int:
        """Token budget for the history window based on the active comm model's context_window."""
        if self.session_factory is None:
            return _DEFAULT_CONTEXT_BUDGET
        try:
            async with self.session_factory() as session:
                setting = await LLMSettingRepository(session, self.redis).get_single_dto()
                if setting is None or setting["user_comm_model_id"] is None:
                    return _DEFAULT_CONTEXT_BUDGET
                model = await LLMModelRepository(session).get(setting["user_comm_model_id"])
                context_window = model.context_window if model and model.context_window else _DEFAULT_CONTEXT_BUDGET
                return max(2000, int(context_window * 0.5))
        except Exception:
            logger.opt(exception=True).warning("context_budget_lookup_failed")
            return _DEFAULT_CONTEXT_BUDGET

    async def maybe_compact(self, conversation_id: str) -> None:
        """Rolling compaction: summarize the oldest unsummarized batch when it
        exceeds the token threshold. Failures are logged and never propagated."""
        try:
            conversation = await self.conversations.find_by_id(conversation_id)
            if conversation is None:
                return
            messages = await self.messages.list_all_before(conversation_id)
            summarized_count = int(conversation.get("summarizedMessageCount", 0))
            unsummarized = messages[summarized_count:]
            if not unsummarized:
                return
            tokens = sum(int(m.get("tokenCount") or _estimate_tokens(str(m.get("content") or ""))) for m in unsummarized if m.get("status") != "failed")
            if tokens < settings.chat_compact_threshold_tokens:
                return
            batch = unsummarized[: -settings.chat_history_window] if len(unsummarized) > settings.chat_history_window else unsummarized
            if len(batch) < 2:
                return
            payload = [{"role": m["role"], "content": str(m["content"])} for m in batch if m.get("content")]
            summarize_prompt = await self._active_prompt(SUMMARIZE)
            result = await self.ai_client.summarize(
                payload,
                previous_summary=str(conversation.get("summary", "")),
                locale=str(conversation.get("locale", "en")),
                prompt=summarize_prompt,
            )
            if not isinstance(result, dict):
                return
            summary = str(result.get("summary", ""))
            if not summary:
                return
            await self.conversations.record_summary(
                conversation_id,
                summary,
                int(cast("Any", result.get("tokens_used") or 0)),
                summarized_count + len(batch),
            )
            logger.info("compaction_done conversation_id={} summarized={} tokens={}", conversation_id, len(batch), tokens)
        except Exception:
            logger.opt(exception=True).warning("compaction_failed conversation_id={}", conversation_id)

    async def maybe_title(self, conversation_id: str, first_query: str, locale: str) -> None:
        """Auto-title from the first user message. Failures are logged, never propagated."""
        try:
            conversation = await self.conversations.find_by_id(conversation_id)
            if conversation is None or conversation.get("title"):
                return
            first = await self.messages.find_first_user_message(conversation_id)
            first_user = str(first.get("content") if first else "").strip() or first_query
            title_prompt = await self._active_prompt(TITLE)
            need_title = bool(conversation.get("needTitle", True))
            result = await self.ai_client.title(first_user, locale=locale, prompt=title_prompt, need_title=need_title)
            if not isinstance(result, dict):
                return
            title = str(result.get("title", "")).strip()
            if not title:
                return
            await self.conversations.set_title(conversation_id, title)
            logger.info("title_set conversation_id={} title={}", conversation_id, title[:80])
        except Exception:
            logger.opt(exception=True).warning("title_failed conversation_id={}", conversation_id)
