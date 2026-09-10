from collections.abc import AsyncGenerator

import httpx
from loguru import logger

from app.core.config import settings
from app.core.error_codes import E
from app.core.exceptions import NotFoundError, ServiceUnavailableError


class AIEngineClient:
    def __init__(self) -> None:
        self.base_url = settings.ai_engine_url
        self.api_key = settings.api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"X-API-Key": self.api_key},
                timeout=300.0,
                trust_env=False,
            )
        return self._client

    def _forward_headers(self, request_id: str = "", user_id: str = "") -> dict[str, str]:
        headers: dict[str, str] = {}
        if request_id:
            headers["X-Request-Id"] = request_id
        if user_id:
            headers["X-User-Id"] = user_id
        return headers

    async def generate_description(
        self,
        product_data: dict[str, object],
        prompt: str | None = None,
        model: str | None = None,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object] | None:
        client = await self._get_client()
        body: dict[str, object] = {"product": product_data}
        if prompt:
            body["prompt"] = prompt
        if model:
            body["model"] = model
        try:
            response = await client.post("/generate-description", json=body, headers=self._forward_headers(request_id, user_id))
            if response.status_code != 200:
                logger.warning("AI Engine generate_description returned {}", response.status_code)
                return None
            data: dict[str, object] | None = response.json()
            return data
        except Exception as exc:
            logger.error("AI Engine generate_description failed: {}", exc)
            return None

    async def health(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        query: str,
        locale: str = "en",
        limit: int = 5,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object]:
        client = await self._get_client()
        response = await client.post(
            "/chat",
            json={"query": query, "locale": locale, "limit": limit},
            headers=self._forward_headers(request_id, user_id),
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def similar_products(
        self,
        product_id: str,
        locale: str = "en",
        limit: int = 10,
        categories: list[list[str]] | None = None,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object]:
        client = await self._get_client()
        response = await client.post(
            "/similar",
            json={"product_id": product_id, "lang": locale, "limit": limit, "categories": categories},
            headers=self._forward_headers(request_id, user_id),
        )
        if response.status_code == 404:
            raise NotFoundError("Product not found in index", translation_key=E.PRODUCT_NOT_FOUND)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def chat_conversational(
        self,
        query: str,
        locale: str,
        history: list[dict[str, object]],
        summary: str = "",
        system_prompt: str | None = None,
        parse_prompt: str | None = None,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object]:
        """Stateless proxy to the AI Engine's history-aware /chat."""
        client = await self._get_client()
        body: dict[str, object] = {
            "query": query,
            "locale": locale,
            "history": history,
            "summary": summary,
        }
        if system_prompt is not None:
            body["system_prompt"] = system_prompt
        if parse_prompt is not None:
            body["parse_prompt"] = parse_prompt
        response = await client.post(
            "/chat",
            json=body,
            headers=self._forward_headers(request_id, user_id),
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def chat_conversational_stream(
        self,
        query: str,
        locale: str,
        history: list[dict[str, object]],
        summary: str = "",
        system_prompt: str | None = None,
        parse_prompt: str | None = None,
        request_id: str = "",
        user_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """SSE frames from the engine for WebSocket relaying."""
        client = await self._get_client()
        payload: dict[str, object] = {
            "query": query,
            "locale": locale,
            "history": history,
            "summary": summary,
            "stream": True,
        }
        if system_prompt is not None:
            payload["system_prompt"] = system_prompt
        if parse_prompt is not None:
            payload["parse_prompt"] = parse_prompt
        async with client.stream(
            "POST",
            "/chat",
            json=payload,
            headers=self._forward_headers(request_id, user_id),
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise ServiceUnavailableError(
                    "AI Engine error",
                    translation_key=E.AI_ENGINE_ERROR,
                    extra={"status": response.status_code, "body": body[:500].decode(errors="replace")},
                )
            async for line in response.aiter_lines():
                line = line.strip()
                if line:
                    yield line

    async def summarize(
        self,
        messages: list[dict[str, object]],
        previous_summary: str = "",
        locale: str = "en",
        prompt: str | None = None,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object]:
        """Rolling compaction: LLM summary of the oldest unsummarized batch."""
        client = await self._get_client()
        body: dict[str, object] = {"messages": messages, "previous_summary": previous_summary, "locale": locale}
        if prompt is not None:
            body["prompt"] = prompt
        response = await client.post(
            "/summarize",
            json=body,
            headers=self._forward_headers(request_id, user_id),
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def title(
        self,
        query: str,
        locale: str = "en",
        prompt: str | None = None,
        need_title: bool = True,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object]:
        """Short conversation title from the first user message."""
        client = await self._get_client()
        body: dict[str, object] = {"query": query, "locale": locale, "need_title": need_title}
        if prompt is not None:
            body["prompt"] = prompt
        response = await client.post(
            "/title",
            json=body,
            headers=self._forward_headers(request_id, user_id),
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def embed_product(
        self,
        product_id: str,
        lang: str,
        text: str,
        webhook_url: str | None = None,
        payload: dict[str, object] | None = None,
        filters: dict[str, list[str]] | None = None,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object] | None:
        client = await self._get_client()
        try:
            response = await client.post(
                "/embed-product",
                json={
                    "product_id": product_id,
                    "lang": lang,
                    "text": text,
                    "webhook_url": webhook_url,
                    "payload": payload,
                    "filters": filters,
                },
                headers=self._forward_headers(request_id, user_id),
            )
            body: dict[str, object] | None = response.json()
            return body
        except Exception as exc:
            logger.warning("AI Engine embed_product failed (fire-and-forget): {}", exc)
            return None

    async def embed_text(
        self,
        text: str,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object] | None:
        client = await self._get_client()
        try:
            response = await client.post(
                "/embed-text",
                json={"text": text},
                headers=self._forward_headers(request_id, user_id),
            )
            body: dict[str, object] | None = response.json()
            return body
        except Exception as exc:
            logger.warning("AI Engine embed_text failed: {}", exc)
            return None

    async def eval_generate_queries(
        self,
        count: int,
        locales: list[str],
        catalog_context: str,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object] | None:
        client = await self._get_client()
        try:
            response = await client.post(
                "/eval/queries",
                json={"count": count, "locales": locales, "catalog_context": catalog_context},
                headers=self._forward_headers(request_id, user_id),
            )
            if response.status_code != 200:
                logger.warning("AI Engine eval_generate_queries returned {}", response.status_code)
                return None
            body: dict[str, object] | None = response.json()
            return body
        except Exception as exc:
            logger.warning("AI Engine eval_generate_queries failed: {}", exc)
            return None

    async def eval_search(
        self,
        query: str,
        locale: str,
        limit: int,
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object] | None:
        client = await self._get_client()
        try:
            response = await client.post(
                "/eval/search",
                json={"query": query, "locale": locale, "limit": limit},
                headers=self._forward_headers(request_id, user_id),
            )
            if response.status_code != 200:
                logger.warning("AI Engine eval_search returned {}", response.status_code)
                return None
            body: dict[str, object] | None = response.json()
            return body
        except Exception as exc:
            logger.warning("AI Engine eval_search failed: {}", exc)
            return None

    async def update_config(
        self,
        config: dict[str, object],
        request_id: str = "",
        user_id: str = "",
    ) -> dict[str, object]:
        client = await self._get_client()
        response = await client.post("/config", json=config, headers=self._forward_headers(request_id, user_id))
        response.raise_for_status()
        data: dict[str, object] = response.json()
        return data

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
