import asyncio
import re
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIEngineClient
from app.core.activity_logger import log_activity
from app.core.config import settings
from app.core.distributed_lock import acquire_lock, release_lock
from app.core.logging import log_source_var
from app.repositories.catalog import AttributeOptionRepository, AttributeRepository
from app.repositories.embedding import ProductEmbeddingRepository
from app.repositories.product_definition import StoreProductRepository
from app.services.embedding_config import get_active_embedding_model
from app.services.product_info_service import get_product_info, minify_product_info

STALE_MINUTES = 2
CYCLE_INTERVAL = 60
BATCH_SIZE = 50

LOCK_KEY = "cron:embedding_recovery"
LOCK_TTL = 600

EMBEDDING_RESULT_PATH = "/api/v1/webhook/embedding-result"


def build_webhook_url() -> str:
    """Build the embedding-result callback URL, appending the shared webhook secret."""
    url = f"{settings.api_base_url}{EMBEDDING_RESULT_PATH}"
    if settings.webhook_secret:
        url = f"{url}?{urlencode({'token': settings.webhook_secret})}"
    return url


GENDER_ATTR_CODES = {
    "target_customer",
    "gender",
    "gender_target",
    "watch_gender_target",
    "eyewear_gender_target",
}

_GENDER_NORMALIZE_MAP = {
    "male": "men",
    "men": "men",
    "man": "men",
    "female": "women",
    "women": "women",
    "woman": "women",
    "girls": "girls",
    "girl": "girls",
    "boys": "boys",
    "boy": "boys",
    "babies": "babies",
    "baby": "babies",
    "kids": "kids",
    "child": "kids",
    "children": "kids",
    "unisex": "unisex",
}

_COLOR_VALUE_ALIAS = {
    "printed": "Multicolor",
    "مطبوع": "متعدد الألوان",
}

SHUTDOWN_EVENT: asyncio.Event | None = None


def set_shutdown_event(event: asyncio.Event) -> None:
    global SHUTDOWN_EVENT
    SHUTDOWN_EVENT = event


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict) and "material" in item:
                mat = item.get("material", "")
                pct = item.get("percentage", 100)
                items.append(f"{mat} ({pct}%)")
            else:
                items.append(str(item))
        return ", ".join(items)
    return str(value)


def _format_flagged_attrs(attributes: list[dict[str, Any]], flagged_codes: set[str]) -> list[str]:
    """Format only the attributes flagged as search-affecting (style discriminators).

    Noise keys (care, sizing, composition, boilerplate) are dropped so the
    embedding text is dominated by look-and-style attributes, not shipping/
    care common text.
    """
    lines: list[str] = []
    for a in attributes:
        code = str(a.get("code", "")).lower()
        if code not in flagged_codes:
            continue
        name = a.get("name", "")
        value = a.get("value")
        if not name or value is None or value == "":
            continue
        formatted = _format_value(value)
        if formatted:
            lines.append(f"- {name}: {formatted}")
    return lines


def _flatten_attr_value(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict) and "material" in item:
                mat = item.get("material", "")
                if mat:
                    items.append(mat)
            elif isinstance(item, str):
                items.append(item)
        return items
    return [str(value)]


def _extract_gender_filter(attributes: list[dict[str, Any]]) -> list[str]:
    """Extract and normalize gender values from product attributes.

    Returns canonical values (men/women/girls/boys/babies/kids/unisex). Falls
    back to ["unisex"] when no gender attribute is present on the product.
    """
    gender_vals: list[str] = []
    for a in attributes if isinstance(attributes, list) else []:
        if str(a.get("code", "")) not in GENDER_ATTR_CODES:
            continue
        for raw in _flatten_attr_value(a.get("value")):
            normalized = _GENDER_NORMALIZE_MAP.get(str(raw).strip().lower())
            if normalized:
                gender_vals.append(normalized)
    if gender_vals:
        return list(set(gender_vals))
    return ["unisex"]


_SIZE_SYSTEMS = {"EU", "US", "UK", "IT", "FR", "JP", "CN"}

_SIZE_WORD_MAP: dict[str, str] = {
    "small": "s",
    "medium": "m",
    "large": "l",
    "extra large": "xl",
    "x large": "xl",
    "extra small": "xs",
    "x small": "xs",
    "one size": "one size",
    "os": "one size",
    "free size": "one size",
    "free": "one size",
    "adjustable": "one size",
    "standard": "one size",
    "standard size": "one size",
}

_SIZE_LETTER_RE = re.compile(r"^(?:x{1,3})?[sml]$")


def _normalize_size_tokens(label: str, system: str | None = None) -> list[str]:
    """Return canonical lowercase size tokens for a product size.

    Letters and words collapse to a canonical token (``M``/``medium`` -> ``m``,
    ``XL``/``extra large`` -> ``xl``), free sizes collapse to ``one size``, and
    numeric sizes keep their raw value plus a system-tagged token when a size
    system is present (``42`` + ``EU`` -> ``["42", "eu:42"]``). The AI Engine
    filter normalizes the user's request to the same token set, so exact
    ``MatchAny`` hits regardless of how the size was written.
    """
    raw = " ".join(str(label).strip().lower().split())
    if not raw:
        return []

    mapped = _SIZE_WORD_MAP.get(raw)
    if mapped:
        return list(dict.fromkeys([mapped, raw]))

    if _SIZE_LETTER_RE.fullmatch(raw):
        return [raw]

    prefixed = re.fullmatch(r"([a-z]{2})\s+(\d+(?:[.,]\d+)?)", raw)
    if prefixed:
        sys_name, num = prefixed.group(1), prefixed.group(2)
        return [num, f"{sys_name}:{num}"]

    if re.fullmatch(r"\d+(?:[.,]\d+)?", raw):
        tokens = [raw]
        if system and str(system).upper() in _SIZE_SYSTEMS:
            tokens.append(f"{str(system).lower()}:{raw}")
        return list(dict.fromkeys(tokens))

    return [raw]


def _category_chain_names(info: dict[str, Any]) -> list[str]:
    """Top-level -> leaf category names for a product info dict.

    product info exposes the chain as ``category`` (top-level) plus
    ``category_parents`` (intermediate + leaf) so the embed text and the
    ``_category`` payload filter carry every level, fixing the dead leaf
    tier (payload previously had only top-level names).
    """
    names: list[str] = []
    cat = info.get("category")
    if cat:
        name = cat.get("name") if isinstance(cat, dict) else str(cat)
        if name:
            names.append(str(name))
    parents = info.get("category_parents") or []
    for parent in parents if isinstance(parents, list) else []:
        name = parent.get("name") if isinstance(parent, dict) else str(parent)
        if name:
            names.append(str(name))
    return names


def _build_flat_filters(en_info: dict[str, Any], ar_info: dict[str, Any]) -> dict[str, list[str]]:
    """Build bilingual flat filter fields for the Qdrant payload.

    Values are collected from both the English and Arabic product info so
    chat filters match regardless of the language the user searched in.
    """
    filters: dict[str, list[str]] = {}

    for info in (en_info, ar_info):
        for cat_name in _category_chain_names(info):
            filters.setdefault("_category", []).append(cat_name)
        brand = info.get("brand")
        if brand:
            filters.setdefault("_brand", []).append(str(brand))

        sizes = info.get("sizes", [])
        for size in sizes if isinstance(sizes, list) else []:
            if isinstance(size, dict):
                label = size.get("label")
                system = size.get("system")
            else:
                label = size
                system = None
            if not label:
                continue
            filters.setdefault("_size", []).extend(_normalize_size_tokens(str(label), str(system) if system else None))

        attrs = info.get("attributes", [])
        for a in attrs if isinstance(attrs, list) else []:
            value = a.get("value")
            if not value:
                continue
            code = str(a.get("code", "")).lower()
            name = str(a.get("name", "")).lower()
            if "color" in code or "colour" in code or "color" in name:
                vals = _flatten_attr_value(value)
                if vals:
                    filters.setdefault("_color", []).extend(vals)
            if "material" in code or "fabric" in code or "material" in name or "fabric" in name:
                vals = _flatten_attr_value(value)
                if vals:
                    filters.setdefault("_material", []).extend(vals)

    if filters.get("_color"):
        filters["_color"] = [_COLOR_VALUE_ALIAS.get(v.strip().lower(), v) for v in filters["_color"]]

    filters["_gender"] = _extract_gender_filter(cast("list[dict[str, Any]]", en_info.get("attributes", [])))

    # Products without any declared size (perfume, jewelry, eyewear, ...) get a
    # canonical "one size" token so size-less queries can still reach them.
    if "_size" not in filters:
        filters["_size"] = ["one size"]

    for key in list(filters.keys()):
        if filters[key]:
            filters[key] = list(dict.fromkeys(filters[key]))
        else:
            del filters[key]
    return filters


async def _fetch_product_color_data(db: AsyncSession, product_id: str) -> tuple[list[str], list[str]]:
    """Collect colors and color families from product attributes AND variants."""
    return await AttributeOptionRepository(db).fetch_color_data(product_id)


def _clean_short_description(text: str | None) -> str | None:
    """Strip boilerplate prefixes from a short description and normalize whitespace.

    Removes leading ``Model height: <cm>`` (EN), ``طول العارض/ة: <cm>`` (AR)
    and ``ZARA WOMAN COLLECTION`` lines that scraper descriptions carry as a
    prefix, keeping the genuine style description. Returns ``None`` when nothing
    meaningful remains.
    """
    if not text or not text.strip():
        return None

    boilerplate_re = re.compile(
        r"^(Model height\s*:\s*\d+(?:\.\d+)?\s*cm[.,]?|"
        r"طول\s+العارض[​\u200c]?/ة\s*:\s*\d+(?:\.\d+)?\s*cm[.,]?|"
        r"ZARA WOMAN COLLECTION)\s*$",
        re.IGNORECASE,
    )

    paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        kept = [line for line in lines if not boilerplate_re.match(line)]
        if not kept:
            continue
        paragraphs.append(" ".join(kept))

    cleaned = "\n\n".join(paragraphs).strip()
    return cleaned if cleaned else None


_PRICE_TIER_LABELS = {
    "en": ["budget", "mid", "premium"],
    "ar": ["اقتصادي", "متوسط", "فاخر"],
}

_SEASON_LABELS = {"en": "seasonal", "ar": "موسمي"}

_SEASON_KEYWORDS = {
    "en": ["season", "summer", "winter", "spring", "fall", "summer collection", "winter collection"],
    "ar": ["موسم", "صيف", "شتاء", "ربيع", "خريف", "موسم صيف", "موسم شتاء"],
}

_OCCASION_KEYWORDS = {
    "en": ["party", "formal", "casual", "work", "office", "date", "night", "evening"],
    "ar": ["حفلة", "رسمي", "كاجوال", "عمل", "مكتب", "موعد", "ليلة", "مساء"],
}

_OCCASION_LABEL_FMT = {"en": "{} occasion", "ar": "مناسبة {}"}


def _get_price_tier_label(price: float | None, currency: str | None, lang: str = "en") -> str | None:
    """Return a price tier label (budget/mid/premium) based on price."""
    if price is None or price <= 0:
        return None
    # Tier thresholds are relative; simple fixed bands:
    if price < 25:
        tier = _PRICE_TIER_LABELS.get(lang, _PRICE_TIER_LABELS["en"])[0]
    elif price < 100:
        tier = _PRICE_TIER_LABELS.get(lang, _PRICE_TIER_LABELS["en"])[1]
    else:
        tier = _PRICE_TIER_LABELS.get(lang, _PRICE_TIER_LABELS["en"])[2]
    return f"{tier} {currency}" if currency else tier


def _get_season_label(info: dict[str, Any], lang: str = "en") -> str | None:
    """Extract season from product attributes or descriptions (one language)."""
    keywords = _SEASON_KEYWORDS.get(lang, _SEASON_KEYWORDS["en"])
    attrs = info.get("attributes", [])
    for a in attrs if isinstance(attrs, list) else []:
        code = str(a.get("code", "")).lower()
        value = str(a.get("value", "")).lower() if a.get("value") else ""
        if any(season_word in code or season_word in value for season_word in keywords):
            return _SEASON_LABELS.get(lang, _SEASON_LABELS["en"])
    sd = info.get("short_description") or ""
    sd_lower = str(sd).lower()
    if any(sw in sd_lower for sw in keywords):
        return _SEASON_LABELS.get(lang, _SEASON_LABELS["en"])
    return None


def _get_occasion_label(info: dict[str, Any], lang: str = "en") -> str | None:
    """Extract occasion/style from product attributes or descriptions (one language)."""
    keywords = _OCCASION_KEYWORDS.get(lang, _OCCASION_KEYWORDS["en"])
    label_fmt = _OCCASION_LABEL_FMT.get(lang, _OCCASION_LABEL_FMT["en"])
    attrs = info.get("attributes", [])
    for a in attrs if isinstance(attrs, list) else []:
        value = str(a.get("value", "")).lower() if a.get("value") else ""
        if any(kw in value for kw in keywords):
            return label_fmt.format(keywords[0])
    sd = info.get("short_description") or ""
    sd_lower = str(sd).lower()
    if any(kw in sd_lower for kw in keywords):
        return label_fmt.format(keywords[0])
    return None


_STRUCTURAL_LABELS = {
    "en": {
        "name": "Name",
        "category": "Category",
        "attributes": "Attributes",
        "price_tier": "Price tier",
        "season": "Season",
        "occasion": "Occasion",
        "short_desc": "Short Description",
    },
    "ar": {
        "name": "الاسم",
        "category": "الفئة",
        "attributes": "الخصائص",
        "price_tier": "فئة السعر",
        "season": "الموسم",
        "occasion": "المناسبة",
        "short_desc": "الوصف المختصر",
    },
}


def _format_embed_text(info: dict[str, Any], flagged_codes: set[str], lang: str = "en") -> str | None:
    """Build the per-language embedding text: name -> category chain -> flagged attributes -> short description.

    Only attributes whose codes are in ``flagged_codes`` (is_search_affecting)
    are included. AI/long descriptions, care instructions, image alt texts,
    price, SKU and brands are REMOVED — they are boilerplate that dominated the
    vector text and biased similarity toward same-brand/description matches.

    Enrichment tokens added (localized to ``lang``):
    - Price tier (budget/mid/premium) extracted from price/currency
    - Seasonal label extracted from attributes/descriptions
    - Occasion/style label extracted from attributes/descriptions

    One passage per language is embedded as its own point (``uuid5(product_id_lang)``)
    so queries in a language match that language's passage, and the BM25 sparse
    vector matches lexical tokens in the right script.
    """
    labels = _STRUCTURAL_LABELS.get(lang, _STRUCTURAL_LABELS["en"])
    parts: list[str] = []

    name = info.get("name")
    if name:
        parts.append(f"{labels['name']}: {name}")

    cat_names = _category_chain_names(info)
    if cat_names:
        parts.append(f"{labels['category']}: " + " / ".join(cat_names))

    attrs = _format_flagged_attrs(info.get("attributes", []), flagged_codes)
    if attrs:
        parts.append(f"{labels['attributes']}:\n" + "\n".join(attrs))

    price_tier = _get_price_tier_label(info.get("price"), info.get("currency"), lang)
    if price_tier:
        parts.append(f"{labels['price_tier']}: {price_tier}")

    season = _get_season_label(info, lang)
    if season:
        parts.append(f"{labels['season']}: {season}")

    occasion = _get_occasion_label(info, lang)
    if occasion:
        parts.append(f"{labels['occasion']}: {occasion}")

    short_desc = _clean_short_description(info.get("short_description"))
    if short_desc:
        parts.append(f"{labels['short_desc']}: {short_desc}")

    text = "\n\n".join(p.strip() for p in parts if p.strip())
    return text if text else None


async def _get_search_affecting_codes(db: AsyncSession) -> set[str]:
    """Return lowercase codes of attributes flagged is_search_affecting=True."""
    attributes = await AttributeRepository(db).list_search_affecting()
    return {str(a.code).lower() for a in attributes}


async def build_embed_data(product_id: str, db: AsyncSession, redis: Redis | None = None) -> tuple[str | None, str | None, dict[str, object], dict[str, list[str]]] | None:
    try:
        en_info = await get_product_info(db, product_id, "en", redis=redis)
    except Exception:
        logger.warning("build_embed_data failed for en product_id={}", product_id, exc_info=True)
        return None

    try:
        ar_info = await get_product_info(db, product_id, "ar", redis=redis)
    except Exception:
        logger.warning("build_embed_data failed for ar product_id={}", product_id, exc_info=True)
        ar_info = {}

    try:
        flagged_codes = await _get_search_affecting_codes(db)
    except Exception:
        logger.warning("build_embed_data failed to load search-affecting codes product_id={}", product_id, exc_info=True)
        flagged_codes = set()

    embed_text_en = _format_embed_text(en_info, flagged_codes, "en")
    embed_text_ar = _format_embed_text(ar_info, flagged_codes, "ar")
    if not embed_text_en and not embed_text_ar:
        return None

    store_id: str | None = None
    try:
        store_id = await StoreProductRepository(db).get_store_id(product_id)
    except Exception:
        logger.exception("Failed to fetch store_id for product_id={}", product_id)

    en_minified = minify_product_info(en_info)
    ar_minified = minify_product_info(ar_info)

    en_images = cast("list[dict[str, Any]]", en_info.get("images", []))
    if en_images:
        first_url = en_images[0].get("url") or en_images[0].get("src")
        if first_url:
            en_minified["image_url"] = first_url

    product_data: dict[str, object] = {
        "en": en_minified,
        "ar": ar_minified,
    }
    if store_id:
        product_data["store_id"] = store_id

    filters = _build_flat_filters(en_info, ar_info)

    try:
        extra_colors, color_families = await _fetch_product_color_data(db, product_id)
    except Exception:
        logger.warning("_fetch_product_color_data failed for product_id={}", product_id, exc_info=True)
        extra_colors, color_families = [], []
    if extra_colors:
        filters["_color"] = list(dict.fromkeys([*filters.get("_color", []), *extra_colors]))
    if color_families:
        filters["_color_family"] = color_families

    return (embed_text_en, embed_text_ar, product_data, filters)


async def _ensure_active_model_rows(db: AsyncSession, model_name: str) -> int:
    """Insert pending rows for products missing an active-model row.

    Preserves the legacy behavior where every product without an embedding
    status was eligible for embedding (including brand-new products).
    """
    return await ProductEmbeddingRepository(db).ensure_active_model_rows(model_name)


async def _fetch_stale_products(db: AsyncSession, model_name: str | None = None, redis: Redis | None = None) -> list[dict[str, str]]:
    if model_name is None:
        model_name, _ = await get_active_embedding_model(db, redis)
    return await ProductEmbeddingRepository(db).fetch_stale(model_name, STALE_MINUTES, BATCH_SIZE)


async def fetch_unembedded_products(
    db: AsyncSession,
    include_errors: bool = False,
    limit: int = 500,
    model_name: str | None = None,
    redis: Redis | None = None,
) -> list[dict[str, str]]:
    if model_name is None:
        model_name, _ = await get_active_embedding_model(db, redis)
    await _ensure_active_model_rows(db, model_name)
    await db.commit()

    return await ProductEmbeddingRepository(db).fetch_unembedded(model_name, include_errors, limit)


async def reindex_active_model(db: AsyncSession, model_name: str) -> int:
    """Mark every product as pending for the given model.

    Used when the embedding model changes (auto re-index) or via the admin
    re-index action. Missing rows are inserted; existing rows are reset to
    pending so the recovery cron re-embeds them into the model's collection.
    """
    count = await ProductEmbeddingRepository(db).reindex_model(model_name)
    logger.info("Re-index requested for model={} affected={}", model_name, count)
    return count


async def _upsert_embedding_status(
    db: AsyncSession,
    product_id: str,
    model_name: str,
    status: str,
    error: str | None = None,
) -> None:
    await ProductEmbeddingRepository(db).upsert_status(
        product_id=product_id,
        model_name=model_name,
        status=status,
        error=error,
    )


async def _claim_embedding_row(
    db: AsyncSession,
    product_id: str,
    model_name: str,
    stale_cutoff: datetime | None = None,
) -> bool:
    """Atomically claim a pending/generating embedding row as 'generating'.

    Only one worker wins per row, so concurrent cron/backfill runs cannot
    double-submit. When `stale_cutoff` is given, only rows not refreshed after
    the cutoff are claimable (prevents re-submitting rows another worker just
    picked up).
    """
    return await ProductEmbeddingRepository(db).claim_row(product_id, model_name, stale_cutoff)


async def _embed_single_product(
    db: AsyncSession,
    product: dict[str, str],
    ai_client: AIEngineClient,
    webhook_url: str | None = None,
    index: int = 0,
    total: int = 0,
    model_name: str | None = None,
    claim_stale_only: bool = False,
    redis: Redis | None = None,
) -> bool:
    pid = product["id"]
    prefix = f"[{index}/{total}]" if total else ""
    if model_name is None:
        model_name, _ = await get_active_embedding_model(db, redis)
    try:
        logger.info("{} Building embed text for product={}", prefix, pid)
        embed_result = await build_embed_data(pid, db, redis=redis)
        if not embed_result:
            logger.warning("{} No embed text for product={} — marking error", prefix, pid)
            await _upsert_embedding_status(db, pid, model_name, "error", "no text content")
            await db.commit()
            return False

        embed_text_en, embed_text_ar, product_data, filters = embed_result
        logger.info("{} Embed texts built (en={} chars, ar={} chars) for product={}", prefix, len(embed_text_en or ""), len(embed_text_ar or ""), pid)

        cutoff = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES) if claim_stale_only else None
        claimed = await _claim_embedding_row(db, pid, model_name, stale_cutoff=cutoff)
        await db.commit()
        if not claimed:
            logger.info("{} Skipping product={} (row claimed by another worker)", prefix, pid)
            return False

        langs: list[tuple[str, str]] = []
        if embed_text_en:
            langs.append(("en", embed_text_en))
        if embed_text_ar:
            langs.append(("ar", embed_text_ar))

        all_ok = True
        for lang, text in langs:
            logger.info("{} Sending to AI Engine for product={} lang={}", prefix, pid, lang)
            resp = await ai_client.embed_product(pid, lang, text, webhook_url, payload=product_data, filters=filters)
            logger.info("{} AI Engine responded for product={} lang={} response={}", prefix, pid, lang, resp)

            if webhook_url is None:
                if resp and resp.get("status") == "ok":
                    continue
                all_ok = False
            elif resp is None:
                all_ok = False

        if webhook_url is None:
            status = "done" if all_ok else "error"
            error_msg: str | None = None if all_ok else "embedding failed"
            logger.info("{} Updating DB status={} for product={}", prefix, status, pid)
            await _upsert_embedding_status(db, pid, model_name, status, error_msg)
            await db.commit()
            logger.info("{} DB updated for product={}", prefix, pid)

        return all_ok
    except Exception as exc:
        logger.error("{} Embedding failed for product={} error={}", prefix, pid, exc)
        if webhook_url is None:
            try:
                await _upsert_embedding_status(db, pid, model_name, "error", str(exc))
                await db.commit()
            except Exception:
                logger.exception("failed to update error status for product={}", pid)
        return False


async def submit_for_embedding(
    db: AsyncSession,
    products: list[dict[str, str]],
    ai_client: AIEngineClient,
    webhook_url: str | None = None,
    model_name: str | None = None,
    claim_stale_only: bool = False,
    redis: Redis | None = None,
) -> int:
    if model_name is None:
        model_name, _ = await get_active_embedding_model(db, redis)
    total = len(products)
    success = 0
    for i, product in enumerate(products, 1):
        ok = await _embed_single_product(db, product, ai_client, webhook_url, model_name=model_name, claim_stale_only=claim_stale_only, redis=redis)
        if ok:
            success += 1
        logger.info("embedding_progress product={} ({}/{}) ok={}", product["id"], i, total, ok)
    logger.info("embedding_complete total={} ok={} failed={}", total, success, total - success)
    return success


async def submit_for_embedding_concurrent(
    session_factory: async_sessionmaker[AsyncSession],
    products: list[dict[str, str]],
    ai_client: AIEngineClient,
    max_concurrency: int = 10,
    model_name: str | None = None,
    claim_stale_only: bool = False,
    redis: Redis | None = None,
) -> int:
    if model_name is None:
        async with session_factory() as db:
            model_name, _ = await get_active_embedding_model(db, redis)
    total = len(products)
    logger.info("embedding_concurrent starting total={} max_concurrency={}", total, max_concurrency)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _worker(product: dict[str, str], idx: int) -> bool:
        async with semaphore, session_factory() as db:
            return await _embed_single_product(
                db,
                product,
                ai_client,
                index=idx,
                total=total,
                model_name=model_name,
                claim_stale_only=claim_stale_only,
                redis=redis,
            )

    results = await asyncio.gather(
        *[_worker(p, i) for i, p in enumerate(products, 1)],
        return_exceptions=True,
    )
    success = 0
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error("embedding_worker_exception product={} error={}", products[i]["id"], r)
        elif r:
            success += 1
    logger.info("embedding_concurrent_done total={} ok={} failed={}", total, success, total - success)
    return success


async def run_embedding_recovery_cron(
    session_factory: async_sessionmaker[AsyncSession],
    ai_client: AIEngineClient,
    redis: Redis,
) -> None:
    log_source_var.set("system")
    logger.info("embedding_recovery_cron_started interval={}s stale_minutes={}", CYCLE_INTERVAL, STALE_MINUTES)

    while True:
        if SHUTDOWN_EVENT and SHUTDOWN_EVENT.is_set():
            logger.info("embedding_recovery_cron_stopped")
            break

        processed = 0
        lock_token: str | None = None
        try:
            lock_token = await acquire_lock(redis, LOCK_KEY, LOCK_TTL)
            if lock_token is None:
                logger.debug("embedding_recovery_lock_miss: another instance is running")
            else:
                logger.info("embedding_recovery_lock_acquired")
                async with session_factory() as db:
                    model_name, _ = await get_active_embedding_model(db, redis)
                    await _ensure_active_model_rows(db, model_name)
                    await db.commit()
                    products = await _fetch_stale_products(db, model_name, redis)
                    if products:
                        logger.info("embedding_recovery found={} stale products to re-submit", len(products))
                        webhook_url = build_webhook_url()
                        processed = await submit_for_embedding(
                            db,
                            products,
                            ai_client,
                            webhook_url=webhook_url,
                            model_name=model_name,
                            claim_stale_only=True,
                            redis=redis,
                        )
                    else:
                        logger.debug("embedding_recovery: no stale products found")
        except Exception as exc:
            logger.error("embedding_recovery_cycle_error: {}", exc)
        finally:
            if lock_token is not None:
                await release_lock(redis, LOCK_KEY, lock_token)
                logger.info("embedding_recovery_lock_released")

        await log_activity(
            session_factory=session_factory,
            actor_type="system",
            action="CRON_RUN",
            status_code=200,
            resource_type="cron",
            resource_id=None,
            message=f"embedding_recovery cycle: processed {processed} products",
            details={"processed": processed} if processed else None,
            path="/system/cron/embedding-recovery",
            method="CRON",
        )

        if SHUTDOWN_EVENT and SHUTDOWN_EVENT.is_set():
            break

        await asyncio.sleep(CYCLE_INTERVAL)
