import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from loguru import logger
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.activity_logger import ActivityLoggerMiddleware
from app.core.auth import EngineAuthMiddleware
from app.core.config import Settings
from app.core.logging import setup_logging
from app.core.middleware import LogContextMiddleware
from app.routers import chat as chat_router
from app.routers import config as config_router
from app.routers import description as description_router
from app.routers import embed as embed_router
from app.routers import embed_text as embed_text_router
from app.routers import eval as eval_router
from app.routers import similar as similar_router
from app.routers import summarize as summarize_router
from app.routers import title as title_router
from app.services.collection_naming import collection_name_for
from app.services.config_manager import ConfigManager
from app.services.embedding.models.base import EmbeddingModel
from app.services.embedding.models.tei import TEIModel
from app.services.embedding.registry import create_embedding_model
from app.services.embedding_client import EmbeddingClient
from app.services.embedding_dims import embedding_dims_for
from app.services.key_service import build_llm_client, resolve_active_api_key
from app.services.rag import RAGService

settings = Settings()

BOOTSTRAP_INITIAL_BACKOFF = 5.0
BOOTSTRAP_MAX_BACKOFF = 60.0
BOOTSTRAP_MAX_ATTEMPTS = 12


async def _bootstrap_loop(app: FastAPI) -> None:
    s: Settings = app.state.settings

    await asyncio.sleep(2)

    # Always ask the API for current settings (idempotent): a persisted runtime
    # config file only means *some* config was saved before — it says nothing
    # about whether LLM models/keys are still current. Skipping on has_config()
    # left stale env-default clients running after every restart.
    logger.info("Bootstrap: requesting current config from API")

    backoff = BOOTSTRAP_INITIAL_BACKOFF
    for attempt in range(1, BOOTSTRAP_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                resp = await client.post(s.api_bootstrap_url)
                resp.raise_for_status()
                logger.info("Bootstrap: API responded with {}", resp.status_code)
        except asyncio.CancelledError:
            logger.info("Bootstrap: cancelled during API call")
            return
        except Exception as exc:
            logger.warning(
                "Bootstrap: API call failed (attempt {}/{}): {} — retrying in {}s",
                attempt,
                BOOTSTRAP_MAX_ATTEMPTS,
                exc,
                backoff,
            )

        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            logger.info("Bootstrap: cancelled during backoff")
            return

        backoff = min(backoff * 2, BOOTSTRAP_MAX_BACKOFF)

    logger.error(
        "Bootstrap: gave up after {} attempts — engine will run without runtime config overrides",
        BOOTSTRAP_MAX_ATTEMPTS,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging(debug=settings.debug)
    logger.info("Starting AI Engine...")

    db_engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    config_manager = ConfigManager(settings.ai_engine_config_path)
    embedding_provider = config_manager.get("embedding_provider") or settings.embedding_provider
    embedding_model_name = config_manager.get("embedding_model") or settings.embedding_model

    resolved_embedding_key = await resolve_active_api_key(
        db_engine,
        embedding_model_name,
        settings.llm_encryption_key,
        settings.openrouter_api_key,
    )

    embedding_model: EmbeddingModel
    if embedding_provider == "tei":
        embedding_model = TEIModel(
            base_url=config_manager.get("embedding_base_url") or settings.tei_base_url,
            model=embedding_model_name,
            dimensions=embedding_dims_for(embedding_model_name, settings.embedding_dimensions),
            api_key=resolved_embedding_key or "",
        )
    else:
        embedding_model = create_embedding_model(
            settings,
            api_key=resolved_embedding_key or settings.openrouter_api_key,
            fallback_base_url=settings.openrouter_base_url,
        )

    qdrant_client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=30,
        trust_env=False,
    )
    default_llm_model_name = config_manager.get("default_llm_model") or settings.llm_model
    comm_llm_model_name = config_manager.get("user_comm_model") or settings.user_comm_model
    llm_client = await build_llm_client(db_engine, default_llm_model_name, settings)
    comm_llm_client = await build_llm_client(db_engine, comm_llm_model_name, settings)
    embedding_client = EmbeddingClient(model=embedding_model)
    rag_service = RAGService(settings, client=qdrant_client)
    rag_service.set_collection(collection_name_for(embedding_client.model_name), embedding_client.dimensions)

    app.state.llm_client = llm_client
    app.state.comm_llm_client = comm_llm_client
    app.state.embedding_client = embedding_client
    app.state.rag_service = rag_service
    app.state.config_manager = config_manager
    app.state.settings = settings
    app.state.db_engine = db_engine

    tunnel_url = config_manager.get("tei_tunnel_url")
    if tunnel_url and embedding_provider == "tei" and isinstance(embedding_model, TEIModel):
        embedding_model.set_base_url(tunnel_url)
        logger.info("Applied runtime TEI tunnel URL from config: {}", tunnel_url)

    bootstrap_task = asyncio.create_task(_bootstrap_loop(app))
    bootstrap_task.add_done_callback(lambda t: logger.error("Bootstrap task crashed: {}", t.exception()) if t.exception() else None)

    try:
        await rag_service.ensure_collection()
        logger.info("Qdrant collection ready")
    except Exception:
        logger.exception("Qdrant collection setup failed — running in degraded mode")
    yield
    logger.info("Shutting down AI Engine...")
    bootstrap_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await bootstrap_task
    await rag_service.close()
    await qdrant_client.close()
    await db_engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(LogContextMiddleware)
app.add_middleware(EngineAuthMiddleware, secret=settings.engine_api_key)
app.add_middleware(ActivityLoggerMiddleware, log_dir=settings.activity_log_dir)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(config_router.router)
app.include_router(description_router.router)
app.include_router(chat_router.router)
app.include_router(embed_router.router)
app.include_router(embed_text_router.router)
app.include_router(eval_router.router)
app.include_router(similar_router.router)
app.include_router(summarize_router.router)
app.include_router(title_router.router)
