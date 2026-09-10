from fastapi import APIRouter, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.datastructures import State

from app.core.config import Settings
from app.core.crypto import decrypt_api_key
from app.services.collection_naming import collection_name_for
from app.services.config_manager import ConfigManager
from app.services.embedding.models.base import EmbeddingModel
from app.services.embedding.models.openrouter import OpenRouterModel
from app.services.embedding.models.sentence_transformer import SentenceTransformerModel
from app.services.embedding.models.tei import TEIModel
from app.services.embedding_client import EmbeddingClient
from app.services.embedding_dims import embedding_dims_for
from app.services.key_service import build_llm_client
from app.services.llm_client import LLMClient
from app.services.rag import RAGService

router = APIRouter(prefix="/config", tags=["config"])


def _create_embedding_model(
    provider: str,
    settings: Settings,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> EmbeddingModel:
    model_name = model or settings.embedding_model
    dimensions = embedding_dims_for(model_name, settings.embedding_dimensions)
    if provider == "sentence_transformer":
        return SentenceTransformerModel(
            model=model_name,
            dimensions=dimensions,
        )
    if provider == "tei":
        return TEIModel(
            base_url=base_url or settings.tei_base_url,
            model=model_name,
            dimensions=dimensions,
            api_key=api_key,
        )
    if provider == "openrouter":
        return OpenRouterModel(
            api_key=api_key,
            base_url=base_url or settings.openrouter_base_url,
            model=model_name,
            dimensions=dimensions,
        )
    msg = f"Unknown embedding_provider: {provider!r}"
    raise ValueError(msg)


def _llm_base_url_for(provider: str, requested: str, settings: Settings) -> str:
    """Resolve the LLM base URL, never honoring arbitrary caller-supplied URLs.

    API keys (encrypted or plain) would otherwise be shipped to an
    attacker-controlled host. Only known providers are allowed; anything else
    falls back to the provider's configured default.
    """
    if provider == "openrouter":
        return settings.openrouter_base_url
    return settings.opencode_zen_base_url


def _apply_tei_base_url(app_state: State, value: object, cm: ConfigManager) -> dict[str, str]:
    """Swap the TEI tunnel base URL live on the active TEI model."""
    if not isinstance(value, str) or not value:
        return {}
    cm.set("tei_tunnel_url", value)
    ec = getattr(app_state, "embedding_client", None)
    if ec is not None and isinstance(ec.model, TEIModel):
        ec.model.set_base_url(value)
    return {"tei_base_url": value}


async def _apply_embedding_provider(
    app_state: State,
    value: object,
    cm: ConfigManager,
    settings: Settings,
) -> dict[str, str]:
    """Rebuild the embedding client and switch the RAG collection to the new model."""
    if not isinstance(value, dict):
        return {}
    provider = value.get("provider")
    if provider not in ("tei", "sentence_transformer", "openrouter"):
        return {}
    cm.set("embedding_provider", provider)
    api_key = str(value.get("api_key") or "")
    if api_key and value.get("api_key_encrypted"):
        try:
            api_key = decrypt_api_key(api_key, settings.llm_encryption_key)
        except Exception as exc:
            logger.error("Failed to decrypt embedding API key: {}", exc)
            api_key = ""
    base_url = str(value.get("base_url") or "")
    model = str(value.get("model") or "")
    model_instance = _create_embedding_model(provider, settings, api_key, base_url, model)
    new_embedding_client = EmbeddingClient(model=model_instance)
    app_state.embedding_client = new_embedding_client
    cm.set("embedding_model", new_embedding_client.model_name)
    cm.set("embedding_base_url", base_url)

    changes: dict[str, str] = {"embedding_provider": provider}
    rag_service: RAGService | None = getattr(app_state, "rag_service", None)
    if rag_service is not None:
        collection = collection_name_for(new_embedding_client.model_name)
        rag_service.set_collection(collection, new_embedding_client.dimensions)
        try:
            await rag_service.ensure_collection()
        except Exception as exc:
            logger.error("Failed to ensure Qdrant collection '{}' after config change: {}", collection, exc)
            rag_service.restore_collection()
            changes["collection_error"] = str(exc)
        else:
            changes["collection"] = collection
            changes["embedding_model"] = new_embedding_client.model_name
    return changes


def _apply_llm_model(
    app_state: State,
    config: dict[str, object],
    cm: ConfigManager,
    settings: Settings,
    config_key: str,
    cm_key: str,
    state_attr: str,
    fallback_model: str,
) -> dict[str, str]:
    """Rebuild one LLM client (default or conversational) from a config entry."""
    entry = config.get(config_key)
    if not isinstance(entry, dict):
        return {}
    model_name = entry.get("model") or fallback_model
    api_key = entry.get("api_key") or ""
    provider = entry.get("provider") or "opencode_zen"
    base_url = _llm_base_url_for(provider, entry.get("base_url") or "", settings)
    cm.set(cm_key, model_name)
    setattr(app_state, state_attr, LLMClient(api_key=api_key, base_url=base_url, model=model_name, provider=provider))
    return {config_key: model_name}


async def _apply_refresh_llm(
    app_state: State,
    config: dict[str, object],
    cm: ConfigManager,
    settings: Settings,
    db_engine: AsyncEngine,
) -> dict[str, str]:
    """Rebuild both LLM clients from DB/env-resolved keys."""
    if not config.get("refresh_llm"):
        return {}
    default_model_name = cm.get("default_llm_model") or settings.llm_model
    app_state.llm_client = await build_llm_client(db_engine, default_model_name, settings)
    comm_model_name = cm.get("user_comm_model") or settings.user_comm_model
    app_state.comm_llm_client = await build_llm_client(db_engine, comm_model_name, settings)
    return {"refresh_llm": "ok"}


async def _apply_config(
    app_state: State,
    config: dict[str, object],
    cm: ConfigManager,
    settings: Settings,
    db_engine: AsyncEngine,
) -> dict[str, str]:
    changes: dict[str, str] = {}
    changes.update(_apply_tei_base_url(app_state, config.get("tei_base_url"), cm))
    changes.update(await _apply_embedding_provider(app_state, config.get("embedding_provider"), cm, settings))
    changes.update(_apply_llm_model(app_state, config, cm, settings, "default_llm_model", "default_llm_model", "llm_client", settings.llm_model))
    changes.update(_apply_llm_model(app_state, config, cm, settings, "user_comm_model", "user_comm_model", "comm_llm_client", settings.user_comm_model))
    changes.update(await _apply_refresh_llm(app_state, config, cm, settings, db_engine))
    return changes


@router.post("")
async def update_config(body: dict[str, object], request: Request) -> dict[str, object]:
    cm: ConfigManager = request.app.state.config_manager
    settings: Settings = request.app.state.settings
    db_engine = request.app.state.db_engine

    changes = await _apply_config(request.app.state, body, cm, settings, db_engine)

    logger.info("Config applied: {}", changes)
    return {"status": "ok", "changes": changes}
