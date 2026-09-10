import asyncio
import contextlib
import json
from typing import cast

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIEngineClient
from app.core.activity_logger import log_activity
from app.core.cache import invalidate_tables
from app.core.distributed_lock import acquire_lock, release_lock
from app.core.logging import log_source_var
from app.models.ai_description_version import AIDescriptionVersion
from app.models.store_product import StoreProduct
from app.repositories.llm import LLMModelRepository, LLMSettingRepository
from app.repositories.product_definition import StoreProductRepository
from app.repositories.settings import PromptTemplateRepository, SystemSettingRepository
from app.services import prompt_defaults
from app.services.product_info_service import get_product_info, minify_product_info

LOCK_KEY = "cron:product_ai_generation"
LOCK_TTL = 600
CYCLE_INTERVAL = 300
CYCLE_TIMEOUT = 300
BATCH_SIZE = 10
MAX_RETRIES = 3
RETRY_DELAYS = [1.0, 3.0, 9.0]

SHUTDOWN_EVENT: asyncio.Event | None = None


def set_shutdown_event(event: asyncio.Event) -> None:
    global SHUTDOWN_EVENT
    SHUTDOWN_EVENT = event


async def _acquire_lock(redis: Redis) -> str | None:
    return await acquire_lock(redis, LOCK_KEY, LOCK_TTL)


async def _release_lock(redis: Redis, token: str) -> None:
    await release_lock(redis, LOCK_KEY, token)


async def _check_cron_enabled(db: AsyncSession, redis: Redis | None = None) -> bool:
    setting = await SystemSettingRepository(db, redis).get_by_key("product_ai_generation_cron")
    return setting["value"] == "true" if setting else False


async def _get_default_model(db: AsyncSession, redis: Redis | None = None) -> str | None:
    setting = await LLMSettingRepository(db, redis).get_single_dto()
    if not setting or not setting["default_llm_model_id"]:
        return None
    model = await LLMModelRepository(db).get(setting["default_llm_model_id"])
    return model.model if model else None


async def _get_active_prompt(db: AsyncSession, type_: str, default: str, redis: Redis | None = None) -> str:
    content = await PromptTemplateRepository(db, redis).get_active_content(type_)
    return content if content is not None else default


DEFAULT_PRE_PROMPT = prompt_defaults.DEFAULT_PRE_PROMPT
DEFAULT_ENDING_PROMPT = prompt_defaults.DEFAULT_ENDING_PROMPT


async def _build_prompt(db: AsyncSession, product_info: dict[str, object], redis: Redis | None = None) -> str:
    pre_prompt = await _get_active_prompt(db, "pre_prompt", DEFAULT_PRE_PROMPT, redis)
    ending_prompt = await _get_active_prompt(db, "ending_prompt", DEFAULT_ENDING_PROMPT, redis)
    return pre_prompt + json.dumps(product_info, indent=2, ensure_ascii=False) + "\n\n" + ending_prompt


async def _process_product(
    db: AsyncSession,
    product: StoreProduct,
    ai_client: AIEngineClient,
    model: str | None,
    redis: Redis | None = None,
) -> None:
    product_info = await get_product_info(db, product.id, "en", redis)
    product_info = minify_product_info(product_info)
    prompt = await _build_prompt(db, product_info, redis)
    minimal_data: dict[str, object] = {"name_en": product.name_en}

    logger.info(
        "cron_sending product={} model={} product_info={} prompt={}",
        product.id,
        model,
        product_info,
        prompt,
    )

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = await ai_client.generate_description(minimal_data, prompt=prompt, model=model)
            if raw is None:
                logger.warning("cron_generate_failed product={} attempt={}", product.id, attempt + 1)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                return

            descriptions = cast("dict[str, str]", raw.get("descriptions", {}))
            model_used = cast("str", raw.get("model", ""))
            logger.info(
                "cron_received product={} raw_response={}",
                product.id,
                raw,
            )

            version = AIDescriptionVersion(
                product_id=product.id,
                description_en=descriptions.get("en"),
                description_ar=descriptions.get("ar"),
                prompt=prompt,
                model=model_used,
            )
            db.add(version)

            product.ai_description_en = descriptions.get("en")
            product.ai_description_ar = descriptions.get("ar")
            await db.commit()
            if redis is not None:
                await invalidate_tables(redis, {"store_products"})
            logger.info("cron_generated product={} model={}", product.id, model_used)
            return

        except Exception as exc:
            last_error = exc
            logger.warning("cron_generate_error product={} attempt={} error={}", product.id, attempt + 1, exc)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])
                continue

    logger.error("cron_generate_failed product={} after {} retries: {}", product.id, MAX_RETRIES, last_error)


async def run_cycle(
    session_factory: async_sessionmaker[AsyncSession],
    ai_client: AIEngineClient,
    redis: Redis,
) -> None:
    processed = 0
    log_source_var.set("system")
    try:
        async with asyncio.timeout(CYCLE_TIMEOUT):
            async with session_factory() as db:
                enabled = await _check_cron_enabled(db, redis)
                if not enabled:
                    logger.info("cron_skipped: product_ai_generation_cron is disabled")
                    return

                model = await _get_default_model(db, redis)
                if not model:
                    logger.info("cron_skipped: no default LLM model configured")
                    return

                logger.info("cron_cycle_start model={}", model)
                failed_ids: set[str] = set()
                while True:
                    if SHUTDOWN_EVENT and SHUTDOWN_EVENT.is_set():
                        logger.info("cron_shutdown: stopping cycle")
                        break

                    products = await StoreProductRepository(db).list_without_ai_description(failed_ids, limit=BATCH_SIZE)
                    if not products:
                        logger.info("cron_cycle_done: no more products without AI descriptions")
                        break

                    for product in products:
                        if SHUTDOWN_EVENT and SHUTDOWN_EVENT.is_set():
                            break
                        logger.info("cron_processing product={} name_en={}", product.id, product.name_en)
                        await _process_product(db, product, ai_client, model, redis)
                        processed += 1
                        if product.ai_description_en is None and product.ai_description_ar is None:
                            failed_ids.add(product.id)

                    await db.commit()

                    if len(products) < BATCH_SIZE:
                        break

                logger.info("cron_cycle_complete processed={}", processed)
    except TimeoutError:
        logger.error("cron_cycle_timeout: exceeded {}s", CYCLE_TIMEOUT)

    await log_activity(
        session_factory=session_factory,
        actor_type="system",
        action="CRON_RUN",
        status_code=200,
        resource_type="cron",
        resource_id=None,
        message=f"product_ai_cron cycle complete: processed {processed} products",
        details={"processed": processed} if processed else None,
        path="/system/cron/product-ai",
        method="CRON",
    )


async def run_product_ai_cron(
    session_factory: async_sessionmaker[AsyncSession],
    ai_client: AIEngineClient,
    redis: Redis,
) -> None:
    log_source_var.set("system")
    logger.info("cron_started interval={}s lock_ttl={}s", CYCLE_INTERVAL, LOCK_TTL)

    while True:
        if SHUTDOWN_EVENT and SHUTDOWN_EVENT.is_set():
            logger.info("cron_stopped")
            break

        lock_token: str | None = None
        try:
            lock_token = await _acquire_lock(redis)
            if lock_token is not None:
                logger.info("cron_lock_acquired")
                await run_cycle(session_factory, ai_client, redis)
                await _release_lock(redis, lock_token)
                logger.info("cron_lock_released")
            else:
                logger.debug("cron_lock_miss: another instance is running")
        except Exception as exc:
            logger.error("cron_cycle_error: {}", exc)
        finally:
            if lock_token is not None:
                with contextlib.suppress(Exception):
                    await _release_lock(redis, lock_token)

        if SHUTDOWN_EVENT and SHUTDOWN_EVENT.is_set():
            break

        logger.info("cron_waiting next_cycle_in={}s", CYCLE_INTERVAL)
        await asyncio.sleep(CYCLE_INTERVAL)
