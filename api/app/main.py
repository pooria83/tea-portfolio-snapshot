import asyncio
import contextlib
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from redis.asyncio import from_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.client import AIEngineClient
from app.api.v1.router import router as v1_router
from app.core.activity_logger import ActivityLoggerMiddleware, drain_activity_tasks
from app.core.broker import init_broker
from app.core.config import settings
from app.core.exception_handlers import (
    app_error_handler,
    auth_error_handler,
    global_exception_handler,
    validation_error_handler,
)
from app.core.exceptions import AppError, AuthenticationError
from app.core.logging import setup_logging, suppress_stdlib_logging
from app.core.metrics import PrometheusMiddleware
from app.core.middleware import (
    RequestIDMiddleware,
    RestrictDocsMiddleware,
    SecurityHeadersMiddleware,
    ShutdownCheckMiddleware,
)
from app.core.openapi import custom_openapi
from app.db.mongo import mongo_db
from app.services.activity_log_cleanup import run_activity_log_cleanup
from app.services.embedding_cron import run_embedding_recovery_cron
from app.services.product_ai_cron import run_product_ai_cron, set_shutdown_event
from app.services.storage_service import StorageService
from app.services.ws_manager import ConnectionManager

_shutdown_event = asyncio.Event()


def _get_openapi_schema() -> dict[str, Any]:
    return custom_openapi(app)


async def _startup(app: FastAPI) -> None:
    setup_logging()
    logger.bind(service=settings.app_name).info("starting_up")

    app.state.redis = await from_url(settings.redis_url, decode_responses=True)

    engine = create_async_engine(settings.database_url, echo=settings.debug, pool_size=10, max_overflow=20, pool_pre_ping=True)
    suppress_stdlib_logging()
    app.state.engine = engine
    app.state.session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        app.state.broker = await init_broker()
        broker_ok = True
    except Exception:
        logger.opt(exception=True).warning("broker_init_failed")
        app.state.broker = None
        broker_ok = False

    app.state.ai_client = AIEngineClient()
    app.state.ws_manager = ConnectionManager()

    app.state.mongo_db = mongo_db
    await mongo_db.connect()
    if mongo_db.enabled:
        await mongo_db.ensure_indexes()

    storages = [
        ("storage", settings.minio_bucket),
        ("temp_storage", settings.minio_temp_bucket),
        ("profile_storage", settings.minio_profile_bucket),
        ("store_storage", settings.minio_store_bucket),
    ]
    storage_ok = True
    for attr_name, bucket in storages:
        try:
            svc = StorageService(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                bucket=bucket,
                secure=settings.minio_secure,
                public_url=settings.minio_public_url,
            )
            await svc.ensure_bucket()
            await svc.set_bucket_public()
            setattr(app.state, attr_name, svc)
        except Exception:
            logger.bind(bucket=bucket).opt(exception=True).warning("storage_init_failed")
            setattr(app.state, attr_name, None)
            storage_ok = False

    set_shutdown_event(_shutdown_event)
    from app.services.embedding_cron import set_shutdown_event as set_embedding_shutdown

    set_embedding_shutdown(_shutdown_event)

    cron_task = asyncio.create_task(run_product_ai_cron(app.state.session_factory, app.state.ai_client, app.state.redis))

    def _on_cron_error(fut: asyncio.Future[None]) -> None:
        exc = fut.exception()
        if exc:
            logger.opt(exception=exc).error("cron_task_crashed error={}", exc)

    cron_task.add_done_callback(_on_cron_error)
    app.state.product_ai_cron = cron_task

    embedding_cron_task = asyncio.create_task(
        run_embedding_recovery_cron(app.state.session_factory, app.state.ai_client, app.state.redis),
    )
    embedding_cron_task.add_done_callback(_on_cron_error)
    app.state.embedding_cron = embedding_cron_task

    activity_cleanup_task = asyncio.create_task(
        run_activity_log_cleanup(app.state.session_factory, _shutdown_event),
    )
    activity_cleanup_task.add_done_callback(_on_cron_error)
    app.state.activity_cleanup = activity_cleanup_task

    logger.bind(redis=True, broker=broker_ok, consumer=broker_ok, database=True, storage=storage_ok).info("ready")


async def _shutdown(app: FastAPI) -> None:
    _shutdown_event.set()
    logger.info("shutting_down")
    await asyncio.sleep(2)

    for task_name in ("product_ai_cron", "embedding_cron", "activity_cleanup"):
        task = getattr(app.state, task_name, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    await drain_activity_tasks()

    if hasattr(app.state, "ws_manager"):
        await app.state.ws_manager.close()

    if hasattr(app.state, "ai_client"):
        await app.state.ai_client.close()
    if hasattr(app.state, "mongo_db"):
        await app.state.mongo_db.close()
    if hasattr(app.state, "broker") and app.state.broker:
        await app.state.broker.close()

    if hasattr(app.state, "redis"):
        await app.state.redis.aclose()
    if hasattr(app.state, "engine"):
        await app.state.engine.dispose()

    logger.info("shutdown_complete")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _startup(app)
    try:
        yield
    finally:
        await _shutdown(app)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    root_path="",
    servers=[{"url": "/", "description": "Local development"}],
    contact={"name": "Engineering", "url": "https://github.com/org/product-graph"},
    license_info={"name": "MIT", "identifier": "MIT"},
)

app.openapi = _get_openapi_schema  # type: ignore[method-assign]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_origin_regex=settings.allowed_origin_regex or (".*" if settings.debug else None),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["authorization", "content-type", "x-api-key", "x-request-id", "x-requested-with"],
    expose_headers=["x-request-id"],
)
app.add_middleware(ShutdownCheckMiddleware, shutdown_event=_shutdown_event)
app.add_middleware(RestrictDocsMiddleware)
app.add_middleware(SecurityHeadersMiddleware, debug=settings.debug)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(ActivityLoggerMiddleware)


app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(AuthenticationError, auth_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(v1_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.webhooks.post("/webhook/product-sync")
async def webhook_product_sync(payload: dict[str, object]) -> dict[str, str]:
    return {"status": "received"}
