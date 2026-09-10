#!/usr/bin/env python3
"""Seed the database with sample users and products."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.password import hash_password
from app.models.base import Base
from app.models.embed_model import EmbedModel
from app.models.llm import LLMModel
from app.models.prompt_template import PromptTemplate
from app.models.scraper_header import ScraperHeader
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.repositories.embedding import EmbedModelRepository
from app.repositories.llm import LLMModelRepository
from app.repositories.settings import PromptTemplateRepository, SystemSettingRepository
from app.repositories.user import UserRepository
from app.services.prompt_defaults import (
    CHAT_ASSISTANT,
    DEFAULT_CHAT_ASSISTANT_PROMPT,
    DEFAULT_ENDING_PROMPT,
    DEFAULT_PARSE_QUERY_PROMPT,
    DEFAULT_PRE_PROMPT,
    DEFAULT_SUMMARIZE_PROMPT,
    DEFAULT_TITLE_PROMPT,
    ENDING_PROMPT,
    PARSE_QUERY,
    PRE_PROMPT,
    SUMMARIZE,
    TITLE,
)
from scripts.seed_cache_invalidation import invalidate_seed_cache

engine = create_async_engine(settings.database_url, echo=False)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        existing = await UserRepository(session).get("admin-seed-id")
        if not existing:
            admin = User(
                id="admin-seed-id",
                email="reviewer@example.invalid",
                username="admin",
                hashed_password=hash_password("<SECRET>"),
                full_name="Admin User",
                role="admin",
            )
            session.add(admin)

        existing_seller = await UserRepository(session).get("seller-seed-id")
        if not existing_seller:
            seller = User(
                id="seller-seed-id",
                email="reviewer@example.invalid",
                username="seller",
                hashed_password=hash_password("<SECRET>"),
                full_name="Seller User",
                role="seller",
                phone="<PHONE_NUMBER>",
            )
            session.add(seller)
        else:
            existing_seller.phone = "<PHONE_NUMBER>"

        await session.commit()

    async with session_factory() as session:
        repo = LLMModelRepository(session)
        models_data = [
            ("opencode_zen", "big-pickle"),
            ("opencode_zen", "mimo-v2.5-free"),
            ("opencode_zen", "hy3-free"),
            ("opencode_zen", "nemotron-3-ultra-free"),
            ("opencode_zen", "nemotron-3.5-lightning-free"),
            ("opencode_zen", "muse-spark-1.2-contributor-free"),
            ("opencode_zen", "laguna-s-2.1-free"),
            ("opencode_zen", "deepseek-v4-flash-free"),
            ("openrouter", "nvidia/nemotron-3-embed-1b:free"),
            ("openrouter", "gpt-oss-20b"),
        ]
        for provider, model_name in models_data:
            if not await repo.exists_by_provider_model(provider, model_name):
                session.add(LLMModel(provider=provider, model=model_name))
        await session.commit()

    async with session_factory() as session:
        repo = EmbedModelRepository(session)
        embed_models_data = [
            ("Qwen3-Embedding-0.6B", "Qwen3 Embedding 0.6B"),
            ("Qwen3-Embedding-4B", "Qwen3 Embedding 4B"),
            ("Qwen3-Embedding-8B", "Qwen3 Embedding 8B"),
            ("F2LLM-v2-4B", "F2LLM v2 4B"),
            ("jina-embeddings-v5-text-small", "Jina v5 text-small"),
            ("BGE-M3", "BGE-M3"),
            ("Nomic Embed v2", "Nomic Embed v2"),
            ("multilingual-e5-large-instruct", "multilingual-e5-large-instruct"),
            ("multilingual-e5-base", "multilingual-e5-base"),
        ]
        for model_name, display_name in embed_models_data:
            if not await repo.exists_by_name(model_name):
                session.add(EmbedModel(model_name=model_name, display_name=display_name))
        await session.commit()

    async with session_factory() as session:
        prompt_repo = PromptTemplateRepository(session)
        prompt_seeds = (
            ("seed-pre-prompt", PRE_PROMPT, DEFAULT_PRE_PROMPT),
            ("seed-ending-prompt", ENDING_PROMPT, DEFAULT_ENDING_PROMPT),
            ("seed-chat-assistant", CHAT_ASSISTANT, DEFAULT_CHAT_ASSISTANT_PROMPT),
            ("seed-parse-query", PARSE_QUERY, DEFAULT_PARSE_QUERY_PROMPT),
            ("seed-summarize", SUMMARIZE, DEFAULT_SUMMARIZE_PROMPT),
            ("seed-title", TITLE, DEFAULT_TITLE_PROMPT),
        )
        for prompt_id, prompt_type, content in prompt_seeds:
            if await prompt_repo.get_active_content(prompt_type) is None:
                session.add(PromptTemplate(id=prompt_id, type=prompt_type, content=content, is_active=True))

        await session.commit()

    async with session_factory() as session:
        repo = SystemSettingRepository(session)
        if await repo.get_by_key("product_ai_generation_cron") is None:
            session.add(SystemSetting(id="seed-ai-cron", key="product_ai_generation_cron", value="true"))

        if await session.get(ScraperHeader, "seed-zara-header") is None:
            session.add(ScraperHeader(id="seed-zara-header", name="zara", header=None, status="ready"))
        await session.commit()

    await engine.dispose()
    await invalidate_seed_cache({"system_settings", "prompt_templates", "llm_models", "llm_api_keys", "embed_models"})
    print("Seed complete: admin + seller users + LLM models + embed models + prompt templates + system settings + scraper headers created.")


if __name__ == "__main__":
    asyncio.run(seed())
