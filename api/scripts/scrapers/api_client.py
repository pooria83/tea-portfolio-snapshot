"""API client for syncing scraped products to the Product Graph API.

Usage:
    client = ScraperAPIClient(db, api_base_url, api_token)
    product_id = await client.sync_product(result_dict)
"""

import asyncio
import hashlib
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.models.attribute_option import AttributeOption
from app.models.scrape_product import ScrapeProduct
from app.repositories.catalog import (
    AttributeOptionRepository,
    AttributeRepository,
    BrandRepository,
    CategoryRepository,
    ImageViewTypeRepository,
    ProductTypeRepository,
)
from app.repositories.product_definition import StoreProductRepository
from app.repositories.scrape_product import ScrapeProductRepository
from app.services.storage_service import StorageService
from scripts.scrapers.mapper import (
    TYPE_SPECIFIC_ATTR_MAP,
    extract_care_items,
    extract_fabric_composition_from_jsonld,
    extract_fit,
    extract_hem,
    extract_main_material_deprecated,
    extract_main_material_from_jsonld,
    extract_neckline,
    extract_pattern,
    extract_sizes,
    extract_sleeve,
    extract_stretch,
    extract_waist_rise,
    infer_modesty_level,
    match_care_instruction,
    normalize_color,
    resolve_category,
    resolve_target_customer,
)

logger.add(sys.stderr, level="INFO")

STORE_ID = settings.zara_scraper_store_id

PRIMARY_COLOR_CODE = "primary_color"
MAIN_MATERIAL_CODE = "main_material"
FABRIC_COMPOSITION_CODE = "fabric_composition"
MODESTY_LEVEL_CODE = "modesty_level"
TARGET_CUSTOMER_CODE = "target_customer"
CARE_INSTRUCTIONS_CODE = "care_instructions"

VARIANT_SIZE_ATTR_MAP: dict[str, str] = {
    "heels_dress_shoes": "shoe_size",
    "sandals_slippers": "shoe_size",
    "athletic_sneakers": "shoe_size",
    "boots": "shoe_size",
    "belts_leather_goods": "belt_size",
}

IMAGE_CACHE_DIR = Path(settings.tea_image_cache_dir)

EXT_TO_CONTENT_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".gif": "image/gif",
}


@dataclass
class ReferenceData:
    product_type_map: dict[str, str] = field(default_factory=dict)
    brand_id: str | None = None
    image_view_type_map: dict[str, str] = field(default_factory=dict)
    category_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    attribute_map: dict[str, str] = field(default_factory=dict)
    multi_select_attr_ids: set[str] = field(default_factory=set)
    option_map: dict[tuple[str, str], str] = field(default_factory=dict)
    color_family_map: dict[str, list[dict[str, str]]] = field(default_factory=dict)


async def load_reference_data(db: Any) -> ReferenceData:
    product_type_map = {code: pid for pid, code in await ProductTypeRepository(db).list_id_code()}

    brand_id: str | None = None
    for brand in await BrandRepository(db).list_all():
        if brand.code == "zara":
            brand_id = str(brand.id)
            break

    image_view_type_map: dict[str, str] = {}
    for vt_id, pt_id in await ImageViewTypeRepository(db).list_by_code("main"):
        if pt_id:
            image_view_type_map[pt_id] = vt_id

    category_map: dict[str, dict[str, Any]] = {}
    for cat_id, name_en, pt_id, parent_id in await CategoryRepository(db).list_minimal():
        category_map[name_en] = {
            "id": cat_id,
            "product_type_id": pt_id,
            "parent_id": parent_id,
        }

    attribute_map: dict[str, str] = {}
    multi_select_attr_ids: set[str] = set()
    for attr_id, code, input_type in await AttributeRepository(db).list_id_code_input():
        attribute_map[code] = attr_id
        if input_type == "multi-select":
            multi_select_attr_ids.add(attr_id)

    option_map: dict[tuple[str, str], str] = {}
    for attr_id, code, opt_id in await AttributeOptionRepository(db).list_minimal():
        option_map[(attr_id, code)] = opt_id

    color_attr_id = attribute_map.get(PRIMARY_COLOR_CODE)
    color_family_map: dict[str, list[dict[str, str]]] = {}
    if color_attr_id:
        for opt_id, code, value_en, family in await AttributeOptionRepository(db).list_color_family_by_attribute(color_attr_id):
            if family not in color_family_map:
                color_family_map[family] = []
            color_family_map[family].append(
                {
                    "id": opt_id,
                    "code": code,
                    "value_en": value_en,
                }
            )

    return ReferenceData(
        product_type_map=product_type_map,
        brand_id=brand_id,
        image_view_type_map=image_view_type_map,
        category_map=category_map,
        attribute_map=attribute_map,
        multi_select_attr_ids=multi_select_attr_ids,
        option_map=option_map,
        color_family_map=color_family_map,
    )


class ScraperAPIClient:
    def __init__(self, db: Any, api_base_url: str, api_token: str = "", api_key: str = "", reference_data: ReferenceData | None = None) -> None:
        self.db = db
        self.api_base_url = api_base_url.rstrip("/")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        elif api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        self._http = httpx.AsyncClient(
            base_url=self.api_base_url,
            headers=headers,
            timeout=120.0,
            trust_env=False,
        )
        self._storage = StorageService(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_temp_bucket,
            secure=settings.minio_secure,
            public_url=settings.minio_public_url,
        )
        self._loaded = False
        self._ref = reference_data

    async def __aenter__(self) -> "ScraperAPIClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._ref is not None:
            self._product_type_map = self._ref.product_type_map
            self._brand_id = self._ref.brand_id
            self._image_view_type_map = self._ref.image_view_type_map
            self._category_map = self._ref.category_map
            self._attribute_map = self._ref.attribute_map
            self._multi_select_attr_ids = self._ref.multi_select_attr_ids
            self._option_map = self._ref.option_map
            self._color_family_map = self._ref.color_family_map
            self._loaded = True
            return
        ref = await load_reference_data(self.db)
        self._product_type_map = ref.product_type_map
        self._brand_id = ref.brand_id
        self._image_view_type_map = ref.image_view_type_map
        self._category_map = ref.category_map
        self._attribute_map = ref.attribute_map
        self._multi_select_attr_ids = ref.multi_select_attr_ids
        self._option_map = ref.option_map
        self._color_family_map = ref.color_family_map
        self._loaded = True

    async def _resolve_id(self, stmt: Any) -> str | None:
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return str(row) if row else None

    async def _resolve_or_create_option(
        self,
        attr_id: str,
        code: str,
        value_en: str,
        *,
        value_ar: str = "",
        value_fa: str = "",
        color_hex: str | None = None,
    ) -> str | None:
        existing = self._option_map.get((attr_id, code))
        if existing:
            return existing
        next_sort = (await AttributeOptionRepository(self.db).max_sort_order(attr_id)) + 1
        new_id = str(uuid.uuid4())
        new_option = AttributeOption(
            id=new_id,
            attribute_id=attr_id,
            code=code,
            value_en=value_en,
            value_ar=value_ar or value_en,
            value_fa=value_fa or value_en,
            sort_order=next_sort,
            color_hex=color_hex,
        )
        await AttributeOptionRepository(self.db).add(new_option)
        self._option_map[(attr_id, code)] = new_id
        logger.warning("Auto-created attribute option: attr={} code={} value_en={}", attr_id, code, value_en)
        return new_id

    async def sync_product(self, result: dict[str, Any]) -> str | None:
        await self._ensure_loaded()
        raw = result.get("raw_data", {})
        source_category = result.get("source_category", "") or ""
        product_name_en = raw.get("en", {}).get("name", "")

        images = raw.get("images", [])
        colors = raw.get("colors", [])
        availability = raw.get("availability", {})
        if isinstance(availability, dict):
            availability = availability.get("skusAvailability", list(availability.values()))
        en_json_ld = raw.get("en", {}).get("json_ld", {})
        extra_detail_en = raw.get("en", {}).get("extra_detail", {}) or {}
        if isinstance(extra_detail_en, list):
            extra_detail_en = extra_detail_en[0] if extra_detail_en else {}
        deprecated_materials = extra_detail_en.get("materials", [])

        images_per_color = raw.get("images_per_color", {})
        has_per_color_images = bool(images_per_color and colors)

        if has_per_color_images:
            upload_result: list[dict[str, Any]] = []
            color_code_to_opt_id: dict[str, str] = {}
            for c in colors:
                raw = normalize_color(c.get("name", c.get("code", "")))
                primary_color_attr_id = self._attribute_map.get(PRIMARY_COLOR_CODE)
                if primary_color_attr_id:
                    match = self._match_color(primary_color_attr_id, raw)
                    if match:
                        color_code_to_opt_id[raw] = match
                    else:
                        color_name = c.get("name", c.get("code", "")).title()
                        created = await self._resolve_or_create_option(primary_color_attr_id, raw, color_name)
                        if created:
                            color_code_to_opt_id[raw] = created
            for color_code, color_images_list in images_per_color.items():
                uploaded = await self._upload_images(
                    color_images_list,
                    f"{result['source_id']}_{color_code}",
                )
                opt_id = color_code_to_opt_id.get(normalize_color(color_code))
                for img in uploaded:
                    if opt_id:
                        img["variant_signature"] = [opt_id]
                upload_result.extend(uploaded)
        else:
            upload_result = await self._upload_images(images, result["source_id"])

        payload = await self._build_payload(
            result,
            source_category,
            product_name_en,
            en_json_ld,
            deprecated_materials,
            colors,
            availability,
            upload_result,
        )

        source_url = result.get("source_url", "") or payload.get("source_url", "")
        if source_url:
            existing_product = await StoreProductRepository(self.db).get_by_store_and_source_url(STORE_ID, source_url)
            if existing_product:
                logger.info("Product already exists for {} (api_product_id={}), skipping creation", source_url, existing_product.id)
                return existing_product.id

        await self.db.commit()
        product_id = await self._post_to_api(payload)
        if product_id:
            await self._store_api_product_id(result["source_id"], result["country"], product_id)

        return product_id

    async def _upload_images(
        self,
        images: list[dict[str, Any]],
        source_id: str,
    ) -> list[dict[str, Any]]:
        async def _process_one(img: dict[str, Any], idx: int) -> dict[str, Any]:
            original_url = img.get("url", "")
            minio_url = None
            if original_url:
                minio_url = await self._download_and_upload(original_url, source_id)
            alt_texts = {}
            meta = img.get("meta")
            if isinstance(meta, dict):
                alt_texts = meta.get("alt_texts", {})
            return {
                "image_url": minio_url or original_url,
                "sort_order": idx,
                "alt_text_en": alt_texts.get("en-US", alt_texts.get("en-GB", "")),
                "alt_text_ar": alt_texts.get("ar-AE", ""),
            }

        tasks = [_process_one(img, idx) for idx, img in enumerate(images[:10]) if img.get("url")]
        return await asyncio.gather(*tasks)

    async def _download_to_cache(self, url: str) -> tuple[Path, str, str] | None:
        """Download image to disk cache. Returns (cache_path, content_type, ext) or None on failure."""
        try:
            ext = _extract_ext_from_url(url)
            cache_key = hashlib.md5(url.encode()).hexdigest() + ext
            cache_path = IMAGE_CACHE_DIR / cache_key

            if cache_path.exists():
                content_type = EXT_TO_CONTENT_TYPE.get(ext, "image/jpeg")
                return cache_path, content_type, ext

            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
                "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.zara.com/",
                "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site",
            }
            resp = await self._http.get(url, headers=headers)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            ext = _guess_extension(content_type)
            data = resp.content
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(data)
            return cache_path, content_type, ext
        except Exception as exc:
            logger.warning("Image download failed for {}: {}", url, exc)
            return None

    async def _upload_from_cache(self, cache_path: Path, content_type: str, ext: str, url: str, source_id: str) -> str | None:
        """Upload a cached image file to MinIO. Returns public URL or None on failure."""
        try:
            data = cache_path.read_bytes()
            file_name = f"{uuid.uuid4()}{ext}"
            metadata = {"source": "zara", "original_url": url, "source_id": source_id}
            await self._storage.upload_file(
                file_name=file_name,
                data=data,
                content_type=content_type,
                metadata=metadata,
            )
            return self._storage.get_public_url(file_name)
        except Exception as exc:
            logger.warning("Image upload failed for {}: {}", url, exc)
            return None

    async def _download_and_upload(self, url: str, source_id: str) -> str | None:
        """Download image (from cache or HTTP) and upload to MinIO. Returns public URL or None."""
        cached = await self._download_to_cache(url)
        if cached is None:
            return None
        cache_path, content_type, ext = cached
        return await self._upload_from_cache(cache_path, content_type, ext, url, source_id)

    async def _build_payload(
        self,
        result: dict[str, Any],
        source_category: str,
        product_name_en: str,
        en_json_ld: dict[str, Any],
        deprecated_materials: list[dict[str, Any]],
        colors: list[dict[str, str]],
        availability: list[dict[str, Any]],
        uploaded_images: list[dict[str, Any]],
    ) -> dict[str, Any]:
        raw = result.get("raw_data", {})
        en = raw.get("en", {})
        ar = raw.get("ar", {})
        ar_json_ld = ar.get("json_ld", {}) or {}

        extra_detail_en = en.get("extra_detail", {}) or {}
        extra_detail_sections: list[dict[str, Any]] = extra_detail_en if isinstance(extra_detail_en, list) else []
        care_items = extract_care_items(extra_detail_sections)

        root_en, child_en, pt_code = resolve_category(source_category, product_name_en)
        if not pt_code or not root_en:
            logger.warning("Unmapped category: {} for {}", source_category, product_name_en)
            return {}

        product_type_id = self._product_type_map.get(pt_code)
        if not product_type_id:
            logger.warning("Unknown product type code: {}", pt_code)
            return {}

        category_id = self._resolve_category_id(root_en, child_en, product_type_id)

        sku = f"ZARA-{result['source_id']}"
        currency = result.get("currency", "KWD")
        price = _extract_price(en_json_ld)
        sizes_raw = extract_sizes(en_json_ld)

        attribute_values: list[dict[str, Any]] = []
        variants: list[dict[str, Any]] = []

        target_customers = resolve_target_customer(source_category)
        for tc in target_customers:
            attr_id = self._attribute_map.get(TARGET_CUSTOMER_CODE)
            opt_id = await self._resolve_or_create_option(attr_id, tc, tc.replace("_", " ").title()) if attr_id else None
            if opt_id and attr_id:
                attribute_values.append({"attribute_id": attr_id, "value": opt_id})

        modesty = infer_modesty_level(source_category)
        if modesty:
            attr_id = self._attribute_map.get(MODESTY_LEVEL_CODE)
            opt_id = await self._resolve_or_create_option(attr_id, modesty, modesty.replace("_", " ").title()) if attr_id else None
            if opt_id and attr_id:
                attribute_values.append({"attribute_id": attr_id, "value": opt_id})

        main_material = extract_main_material_from_jsonld(en_json_ld) or extract_main_material_deprecated(deprecated_materials)
        if main_material:
            attr_id = self._attribute_map.get(MAIN_MATERIAL_CODE)
            opt_id = await self._resolve_or_create_option(attr_id, main_material, main_material.replace("_", " ").title()) if attr_id else None
            if opt_id and attr_id:
                attribute_values.append({"attribute_id": attr_id, "value": opt_id})

        fabric_comp = extract_fabric_composition_from_jsonld(en_json_ld)
        if fabric_comp:
            attr_id = self._attribute_map.get(FABRIC_COMPOSITION_CODE)
            if attr_id:
                structured = await self._format_structured_composition(attr_id, fabric_comp)
                attribute_values.append({"attribute_id": attr_id, "value": structured or fabric_comp})

        color_options = await self._resolve_colors(colors)
        for opt_id in color_options:
            attr_id = self._attribute_map.get(PRIMARY_COLOR_CODE)
            if attr_id and opt_id:
                attribute_values.append({"attribute_id": attr_id, "value": opt_id})

        variant_list = en_json_ld.get("hasVariant", [])
        if isinstance(variant_list, dict):
            variant_list = [variant_list]

        size_attr_code = VARIANT_SIZE_ATTR_MAP.get(pt_code or "", "size")
        size_attr_id = self._attribute_map.get(size_attr_code)
        if size_attr_id and variant_list:
            seen_size_labels: set[str] = set()
            for v in variant_list:
                v_size = v.get("size", "")
                if v_size and v_size not in seen_size_labels:
                    seen_size_labels.add(v_size)
                    size_code = self._normalize_variant_size(v_size, size_attr_code)
                    size_label = v_size.upper() if size_attr_code != "shoe_size" else f"EU {v_size}"
                    size_opt_id = await self._resolve_or_create_option(size_attr_id, size_code, size_label)
                    if size_opt_id:
                        attribute_values.append({"attribute_id": size_attr_id, "value": size_opt_id})

        description = en_json_ld.get("description", "")
        await self._add_type_specific_attributes(attribute_values, pt_code, product_name_en, description)

        care_instructions_attr_id = self._attribute_map.get(CARE_INSTRUCTIONS_CODE)
        if care_instructions_attr_id and care_items:
            for care_text in care_items:
                matched = match_care_instruction(care_text)
                if matched:
                    opt_id = await self._resolve_or_create_option(care_instructions_attr_id, matched, matched.replace("_", " ").title())
                    if opt_id:
                        attribute_values.append({"attribute_id": care_instructions_attr_id, "value": opt_id})

        aggregated: dict[str, list[str]] = {}
        single: list[dict[str, Any]] = []
        for av in attribute_values:
            if av["attribute_id"] in self._multi_select_attr_ids:
                aggregated.setdefault(av["attribute_id"], []).append(av["value"])
            else:
                single.append(av)
        attribute_values = single
        for attr_id_multi, values in aggregated.items():
            attribute_values.append(
                {
                    "attribute_id": attr_id_multi,
                    "value": json.dumps(values),
                }
            )

        has_multiple_colors = raw.get("has_multiple_colors", False)

        if variant_list and len(variant_list) > 0:
            variants = await self._build_variants(
                variant_list,
                availability,
                has_multiple_colors,
                colors,
                color_options,
                pt_code,
            )

        images_out: list[dict[str, Any]] = []
        for idx, img in enumerate(uploaded_images):
            entry: dict[str, Any] = {
                "image_url": img["image_url"],
                "sort_order": idx,
            }
            view_type_id = self._image_view_type_map.get(product_type_id) if product_type_id else None
            if view_type_id:
                entry["view_type_id"] = view_type_id
            if img.get("variant_signature"):
                entry["variant_signature"] = img["variant_signature"]
            if img.get("alt_text_en"):
                entry["alt_text_en"] = img["alt_text_en"]
            if img.get("alt_text_ar"):
                entry["alt_text_ar"] = img["alt_text_ar"]
            images_out.append(entry)

        payload: dict[str, Any] = {
            "product_type_id": product_type_id,
            "category_id": category_id,
            "brand": self._brand_id,
            "sku": sku,
            "status": "draft",
            "price": price,
            "currency": currency,
            "quantity": self._total_quantity(variants),
            "name_en": product_name_en,
            "name_ar": ar_json_ld.get("name", ar.get("name", "")),
            "short_description_en": en_json_ld.get("description", ""),
            "short_description_ar": ar_json_ld.get("description", ar.get("description", "")),
            "long_description_en": _build_long_description(en, deprecated_materials, en_json_ld),
            "long_description_ar": _build_long_description(ar, deprecated_materials, ar_json_ld),
            "sizes": sizes_raw,
            "attribute_values": attribute_values,
            "variants": variants,
            "images": images_out,
            "source_url": result.get("source_url") or None,
        }

        return {k: v for k, v in payload.items() if v is not None and v != []}

    def _resolve_category_id(self, root_en: str, child_en: str | None, product_type_id: str) -> str | None:
        if child_en:
            child_info = self._category_map.get(child_en)
            if child_info and child_info.get("parent_id"):
                return str(child_info["id"])
        root_info = self._category_map.get(root_en)
        if root_info and root_info["product_type_id"] == product_type_id:
            return str(root_info["id"])
        for _name, info in self._category_map.items():
            if info["product_type_id"] == product_type_id and info.get("parent_id") is None:
                return str(info["id"])
        return None

    async def _add_type_specific_attributes(
        self,
        attribute_values: list[dict[str, Any]],
        pt_code: str,
        product_name_en: str,
        description: str = "",
    ) -> None:
        type_map = TYPE_SPECIFIC_ATTR_MAP.get(pt_code, {})
        if not type_map:
            return
        added: set[str] = set()
        for text in (product_name_en, description):
            if not text:
                continue
            for attr_type, attr_code in type_map.items():
                if attr_code in added:
                    continue
                attr_id = self._attribute_map.get(attr_code)
                if not attr_id:
                    continue
                val = self._extract_attr_value(attr_type, text)
                if not val:
                    continue
                opt_id = await self._resolve_or_create_option(attr_id, val, val.replace("_", " ").title())
                if opt_id:
                    attribute_values.append({"attribute_id": attr_id, "value": opt_id})
                    added.add(attr_code)

    @staticmethod
    def _extract_attr_value(attr_type: str, text: str) -> str | None:
        if attr_type == "sleeve":
            return extract_sleeve(text)
        if attr_type == "neckline":
            return extract_neckline(text)
        if attr_type == "fit":
            return extract_fit(text)
        if attr_type == "hem":
            return extract_hem(text)
        if attr_type == "pattern":
            return extract_pattern(text)
        if attr_type == "stretch":
            return extract_stretch(text)
        if attr_type == "rise":
            return extract_waist_rise(text)
        return None

    async def _format_structured_composition(self, attr_id: str, text: str) -> str | None:
        """Parse '94% cotton, 6% elastane' into structured JSON for CompositionInput.

        Returns JSON string like:
          [{"material": "<uuid>", "percentage": 94}, {"material": "<uuid>", "percentage": 6}]
        or None if parsing fails (falls back to raw text).
        """
        parts = [p.strip() for p in text.split(",")]
        entries: list[dict[str, object]] = []
        for part in parts:
            m = re.search(r"(\d+)%\s+(.+)", part)
            if m:
                material_name = m.group(2).strip().lower()
                opt_id = await self._resolve_or_create_option(attr_id, material_name, material_name.replace("_", " ").title())
                if opt_id:
                    entries.append({"material": opt_id, "percentage": int(m.group(1))})
        if not entries:
            return None
        return json.dumps(entries)

    async def _resolve_colors(self, colors: list[dict[str, str]]) -> list[str]:
        attr_id = self._attribute_map.get(PRIMARY_COLOR_CODE)
        if not attr_id:
            return []
        option_ids: list[str] = []
        for c in colors:
            raw = normalize_color(c.get("name", c.get("code", "")))
            match = self._match_color(attr_id, raw)
            if match and match not in option_ids:
                option_ids.append(match)
                continue
            for part in raw.split("/"):
                part = part.strip()
                if not part:
                    continue
                match = self._match_color(attr_id, part)
                if match and match not in option_ids:
                    option_ids.append(match)
                    break
            if raw not in option_ids:
                color_name = c.get("name", c.get("code", "")).title()
                created = await self._resolve_or_create_option(attr_id, raw, color_name)
                if created and created not in option_ids:
                    option_ids.append(created)
        return option_ids

    def _match_color(self, attr_id: str, raw: str) -> str | None:
        direct = self._option_map.get((attr_id, raw.replace("-", "_")))
        if direct:
            return direct
        direct = self._option_map.get((attr_id, raw))
        if direct:
            return direct
        for _family, options in self._color_family_map.items():
            for opt in options:
                norm_value = normalize_color(opt["value_en"])
                if raw in norm_value or norm_value in raw:
                    return opt["id"]
        for _family, options in self._color_family_map.items():
            for opt in options:
                if opt["code"] and opt["code"].replace("_", "-") in raw:
                    return opt["id"]
        return None

    async def _build_variants(
        self,
        variant_list: list[dict[str, Any]],
        availability: list[dict[str, Any]],
        has_multiple_colors: bool,
        colors: list[dict[str, str]],
        color_options: list[str],
        pt_code: str | None = None,
    ) -> list[dict[str, Any]]:
        color_code_to_opt_id: dict[str, str] = {}
        if has_multiple_colors and color_options:
            attr_id = self._attribute_map.get(PRIMARY_COLOR_CODE)
            for c in colors:
                raw = normalize_color(c.get("name", c.get("code", "")))
                if attr_id:
                    matched = self._match_color(attr_id, raw)
                    if matched:
                        color_code_to_opt_id[c["code"]] = matched

        size_attr_code = VARIANT_SIZE_ATTR_MAP.get(pt_code or "", "size")
        size_attr_id = self._attribute_map.get(size_attr_code)

        variants: list[dict[str, Any]] = []
        for i, v in enumerate(variant_list):
            av = availability[i] if i < len(availability) else {}
            is_active = av.get("availability", "") == "in_stock"
            quantity = av.get("quantity", 10) if is_active else 0
            offers = v.get("offers", {})
            price = offers.get("price") if isinstance(offers, dict) else None
            opt_ids: list[str] = []
            if has_multiple_colors and color_code_to_opt_id:
                v_color = v.get("color", {})
                color_code = str(v_color.get("id", "")) if isinstance(v_color, dict) else str(v_color or "")
                matched_opt_id = color_code_to_opt_id.get(color_code)
                if matched_opt_id:
                    opt_ids.append(matched_opt_id)
            if size_attr_id:
                v_size = v.get("size", "")
                if v_size:
                    size_code = self._normalize_variant_size(v_size, size_attr_code)
                    size_label = v_size.upper() if size_attr_code != "shoe_size" else f"EU {v_size}"
                    size_opt_id = await self._resolve_or_create_option(size_attr_id, size_code, size_label)
                    if size_opt_id:
                        opt_ids.append(size_opt_id)
            variants.append(
                {
                    "sku": str(v.get("sku", v.get("mpn", f"VAR-{i}"))),
                    "price": float(price) if price else None,
                    "quantity": quantity,
                    "is_active": is_active,
                    "attribute_option_ids": opt_ids,
                }
            )
        return variants

    @staticmethod
    def _normalize_variant_size(size: str, attr_code: str) -> str:
        if attr_code == "shoe_size":
            return f"eu_{size}"
        return size.lower().replace(" ", "_")

    def _total_quantity(self, variants: list[dict[str, Any]]) -> int:
        return sum(v.get("quantity", 0) for v in variants)

    async def _post_to_api(self, payload: dict[str, Any]) -> str | None:
        url = f"/api/v1/stores/{STORE_ID}/products"
        try:
            resp = await self._http.post(url, json=payload)
            if resp.status_code in (200, 201):
                data = resp.json()
                product_id: str | None = data.get("data", {}).get("id")
                if product_id:
                    logger.info("API created product {}", product_id)
                    return product_id
                logger.warning("API response missing product id: {}", data)
                return None
            logger.error("API error {}: {}", resp.status_code, resp.text[:500])
            return None
        except httpx.RequestError as exc:
            logger.error("API request failed: {}", exc)
            return None

    async def _store_api_product_id(self, source_id: str, country: str, product_id: str) -> None:
        sp = await ScrapeProductRepository(self.db).get_by_key("zara", source_id, country)
        if sp:
            sp.api_product_id = product_id
            await self.db.flush()
            await self.db.commit()

    async def sync_pending(self, limit: int = 0, source: str = "", concurrency: int = 5) -> dict[str, Any]:
        await self._ensure_loaded()
        products = await ScrapeProductRepository(self.db).list_pending_sync(limit=limit, source=source)
        if not products:
            return {"created": 0, "errors": 0, "total": 0}

        logger.info("Syncing {} products with concurrency={}", len(products), concurrency)

        ref = ReferenceData(
            product_type_map=self._product_type_map,
            brand_id=self._brand_id,
            image_view_type_map=self._image_view_type_map,
            category_map=self._category_map,
            attribute_map=self._attribute_map,
            multi_select_attr_ids=self._multi_select_attr_ids,
            option_map=self._option_map,
            color_family_map=self._color_family_map,
        )

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        engine = create_async_engine(settings.database_url, echo=False, pool_size=concurrency + 2)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        sem = asyncio.Semaphore(concurrency)
        created = 0
        errors = 0
        lock = asyncio.Lock()

        async def _sync_one(sp: ScrapeProduct) -> None:
            nonlocal created, errors
            async with sem, factory() as session:
                client = ScraperAPIClient(
                    db=session,
                    api_base_url=self.api_base_url,
                    api_token="",
                    api_key=self._http.headers.get("X-API-Key", ""),
                    reference_data=ref,
                )
                try:
                    pid = await client.sync_product(
                        {
                            "source": sp.source,
                            "source_id": sp.source_id,
                            "source_url": sp.source_url or "",
                            "source_category": sp.source_category or "",
                            "country": sp.country,
                            "currency": sp.currency or "",
                            "raw_data": sp.raw_data,
                        }
                    )
                    async with lock:
                        if pid:
                            created += 1
                        else:
                            errors += 1
                except Exception as exc:
                    async with lock:
                        errors += 1
                    logger.exception("Error syncing {}: {}", sp.source_id, exc)
                finally:
                    await client.close()

        tasks = [_sync_one(sp) for sp in products]
        await asyncio.gather(*tasks)
        await engine.dispose()
        return {"created": created, "errors": errors, "total": len(products)}


def _extract_price(json_ld: dict[str, Any]) -> float | None:
    offers = json_ld.get("offers", {})
    if isinstance(offers, dict):
        price = offers.get("price")
        if price:
            return float(price)
    variants = json_ld.get("hasVariant", [])
    if isinstance(variants, list) and variants:
        first = variants[0]
        if isinstance(first, dict):
            v_offers = first.get("offers", {})
            if isinstance(v_offers, dict):
                price = v_offers.get("price")
                if price:
                    return float(price)
    return None


def _build_long_description(
    lang_data: dict[str, Any],
    deprecated_materials: list[dict[str, Any]],
    json_ld: dict[str, Any],
) -> str | None:
    parts: list[str] = []
    extra_detail = lang_data.get("extra_detail", {}) or {}
    care_texts: list[str] = []
    if isinstance(extra_detail, list):
        care_texts = extract_care_items(extra_detail)
    elif isinstance(extra_detail, dict):
        ci = extra_detail.get("careInstructions", "")
        if ci:
            care_texts = [ci]
    if care_texts:
        parts.append(f"CARE: {'; '.join(care_texts)}")
    comp = extract_fabric_composition_from_jsonld(json_ld)
    if not comp and deprecated_materials:
        comp = extract_main_material_deprecated(deprecated_materials)
    if comp:
        parts.append(f"COMPOSITION: {comp}")
    return "\n".join(parts) if parts else None


def _guess_extension(content_type: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/avif": ".avif",
        "image/gif": ".gif",
    }
    return mapping.get(content_type.split(";")[0].strip(), ".jpg")


def _extract_ext_from_url(url: str) -> str:
    """Extract file extension from a URL path, e.g. '.../img.jpg?ts=123' -> '.jpg'."""
    path = url.split("?", 1)[0].rstrip("/")
    _, dot, suffix = path.rpartition(".")
    return f".{suffix}" if dot else ".jpg"
