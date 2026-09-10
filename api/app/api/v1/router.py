from fastapi import APIRouter

from app.api.v1 import anonymous_chat, auth, categories, chats, favorites, files, health, product_definition, product_info, products, public_products, store_types, stores, users, webhooks, ws
from app.api.v1.admin import ai_engine, conversations, cron_products, embed_models, llm, prompt_templates, scraper_headers, search_eval, system_settings

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(favorites.router)
router.include_router(product_definition.public_router)
router.include_router(products.router)
router.include_router(public_products.router)
router.include_router(ws.router)
router.include_router(files.router)
router.include_router(categories.router)
router.include_router(store_types.router)
router.include_router(stores.router)
router.include_router(product_definition.store_router)
router.include_router(product_info.router)
router.include_router(chats.router)
router.include_router(anonymous_chat.router)
router.include_router(llm.router)
router.include_router(embed_models.router)
router.include_router(prompt_templates.router)
router.include_router(system_settings.router)
router.include_router(ai_engine.router)
router.include_router(search_eval.router)
router.include_router(cron_products.router)
router.include_router(conversations.router)
router.include_router(scraper_headers.router)
router.include_router(webhooks.router)
