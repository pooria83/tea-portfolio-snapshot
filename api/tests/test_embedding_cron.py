from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIEngineClient
from app.models.product_embedding import ProductEmbedding
from app.repositories.catalog import _extract_option_uuids
from app.services.embedding_config import DEFAULT_EMBEDDING_MODEL
from app.services.embedding_cron import (
    _build_flat_filters,
    _clean_short_description,
    _embed_single_product,
    _extract_gender_filter,
    _fetch_product_color_data,
    _fetch_stale_products,
    _format_embed_text,
    _normalize_size_tokens,
    fetch_unembedded_products,
)

STORE_ID = "00000000-0000-0000-0000-000000000000"


@pytest_asyncio.fixture
async def seed_embedding_products(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(minutes=5)
    recent = now - timedelta(seconds=30)

    await db_session.execute(
        sa.text("""
            INSERT INTO users (id, email, role, hashed_password, phone, is_active, preferred_language)
            VALUES ('00000000-0000-0000-0000-000000000001', 'embed-test@test.com', 'seller', 'dummy_hash', '+966500000001', true, 'ar')
            ON CONFLICT (id) DO NOTHING
        """)
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO product_types (id, code, name_ar, name_en, name_fa, sort_order)
            VALUES ('pt-embed-test', 'embed-test', 'اختبار', 'Test', 'تست', 0)
            ON CONFLICT (id) DO NOTHING
        """)
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO categories (id, product_type_id, name_ar, name_en, name_fa, sort_order, is_active)
            VALUES ('cat-embed-test', 'pt-embed-test', 'اختبار', 'Test', 'تست', 0, true)
            ON CONFLICT (id) DO NOTHING
        """)
    )
    await db_session.execute(
        sa.text("""
            INSERT INTO store_types (id, name_ar, name_en, name_fa, is_active)
            VALUES ('st-embed-test', 'اختبار', 'Test', 'تست', true)
            ON CONFLICT (id) DO NOTHING
        """)
    )
    await db_session.execute(
        sa.text(f"""
            INSERT INTO stores (id, owner_id, name, category_id, store_type_id, phone, address, location_lat, location_lng, country_code, price_unit_code, is_active)
            VALUES ('{STORE_ID}', '00000000-0000-0000-0000-000000000001', 'Test Store',
                    'cat-embed-test', 'st-embed-test', '+966500000000', 'Test address',
                    24.7136, 46.6753, 'SA', 'SAR', true)
            ON CONFLICT (id) DO NOTHING
        """)
    )

    products = [
        ("sp-stale-pending", "pending", old),
        ("sp-stale-generating", "generating", old),
        ("sp-recent-pending", "pending", recent),
        ("sp-done", "done", old),
        ("sp-error", "error", old),
    ]

    for pid, status, updated_at in products:
        await db_session.execute(
            sa.text(f"""
                INSERT INTO store_products (id, store_id, product_type_id, category_id, status, has_variants, is_multi_piece, quantity, low_stock_threshold, currency, weight_unit, name_en, updated_at, created_at)
                VALUES (:id, '{STORE_ID}', 'pt-embed-test', 'cat-embed-test', 'draft', false, false, 0, 5, 'SAR', 'kg', :name, :updated_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """),  # noqa: E501
            {"id": pid, "name": pid, "updated_at": updated_at},
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO product_embeddings (id, product_id, model_name, embedding_status, updated_at)
                VALUES (md5(:pid || ':' || :model), :pid, :model, :status, :updated_at)
                ON CONFLICT (product_id, model_name) DO UPDATE SET
                    embedding_status = :status,
                    updated_at = :updated_at
            """),  # noqa: E501
            {
                "pid": pid,
                "model": DEFAULT_EMBEDDING_MODEL,
                "status": status,
                "updated_at": updated_at,
            },
        )

    await db_session.commit()


@pytest.mark.asyncio
async def test_fetch_stale_products_returns_stale_pending(
    db_session: AsyncSession,
    seed_embedding_products: None,
) -> None:
    results = await _fetch_stale_products(db_session)
    ids = [r["id"] for r in results]
    assert "sp-stale-pending" in ids
    assert "sp-stale-generating" in ids


@pytest.mark.asyncio
async def test_fetch_stale_products_excludes_recent(
    db_session: AsyncSession,
    seed_embedding_products: None,
) -> None:
    results = await _fetch_stale_products(db_session)
    ids = [r["id"] for r in results]
    assert "sp-recent-pending" not in ids


@pytest.mark.asyncio
async def test_fetch_stale_products_excludes_done_and_error(
    db_session: AsyncSession,
    seed_embedding_products: None,
) -> None:
    results = await _fetch_stale_products(db_session)
    ids = [r["id"] for r in results]
    assert "sp-done" not in ids
    assert "sp-error" not in ids


class TestCleanShortDescription:
    def test_removes_model_height_prefix_en(self) -> None:
        assert _clean_short_description("Model height: 178 cm\n\nT-shirt with round neck.") == ("T-shirt with round neck.")

    def test_removes_model_height_prefix_ar(self) -> None:
        assert _clean_short_description("طول العارض/ة: 178 cm\n\nتيشرت بياقة دائرية.") == ("تيشرت بياقة دائرية.")

    def test_removes_model_height_and_zara_collection(self) -> None:
        text = "Model height: 176 cm\n\nZARA WOMAN COLLECTION\n\nLapelless blazer with long sleeves."
        assert _clean_short_description(text) == "Lapelless blazer with long sleeves."

    def test_keeps_description_without_boilerplate(self) -> None:
        text = "Plain round neck jumper with long sleeves."
        assert _clean_short_description(text) == "Plain round neck jumper with long sleeves."

    def test_removes_floating_zara_collection_anywhere(self) -> None:
        text = "Blazer.\n\nZARA WOMAN COLLECTION\n\nTonal lining."
        assert _clean_short_description(text) == "Blazer.\n\nTonal lining."

    def test_returns_none_for_empty(self) -> None:
        assert _clean_short_description(None) is None
        assert _clean_short_description("") is None
        assert _clean_short_description("   \n  ") is None

    def test_returns_none_when_only_boilerplate(self) -> None:
        assert _clean_short_description("Model height: 180 cm") is None

    def test_collapses_inner_whitespace(self) -> None:
        assert _clean_short_description("Cotton\n\n  dress with\n  flared hem  ") == ("Cotton\n\ndress with flared hem")


class TestFormatEmbedText:
    FLAGGED = {"primary_color", "pattern", "neckline", "dress_style", "main_material"}

    @classmethod
    def fmt(cls, info: dict, lang: str = "en") -> str | None:
        return _format_embed_text(info, cls.FLAGGED, lang)

    def test_empty_both(self) -> None:
        assert self.fmt({}) is None
        assert self.fmt({}, "ar") is None

    def test_name_category_chain_and_short_description_en(self) -> None:
        en = {
            "name": "Dress",
            "category": {"name": "Dresses"},
            "category_parents": [{"name": "Casual Dresses"}],
            "short_description": "Elegant dress",
            "long_description": "A long desc",
        }
        result = self.fmt(en, "en")
        assert result is not None
        assert "Name: Dress" in result
        assert "Category: Dresses / Casual Dresses" in result
        assert "Short Description: Elegant dress" in result
        assert "Long Description" not in result
        assert "Name (EN)" not in result

    def test_name_category_chain_and_short_description_ar(self) -> None:
        ar = {
            "name": "فستان",
            "category": {"name": "فساتين"},
            "category_parents": [{"name": "فساتين كاجوال"}],
            "short_description": "فستان أنيق",
            "long_description": "وصف طويل",
        }
        result = self.fmt(ar, "ar")
        assert result is not None
        assert "الاسم: فستان" in result
        assert "الفئة: فساتين / فساتين كاجوال" in result
        assert "الوصف المختصر: فستان أنيق" in result
        assert "وصف طويل" not in result

    def test_only_flagged_attributes_included_en(self) -> None:
        en = {
            "name": "Dress",
            "attributes": [
                {"code": "primary_color", "name": "Color", "value": "Red"},
                {"code": "neckline", "name": "Neckline", "value": "V-Neck"},
                {"code": "care_instructions", "name": "Care", "value": "Machine wash cold"},
                {"code": "fabric_composition", "name": "Composition", "value": "100% Cotton"},
                {"code": "fashion_tags", "name": "Tags", "value": "Trendy"},
            ],
        }
        result = self.fmt(en, "en")
        assert result is not None
        assert "Attributes:" in result
        assert "- Color: Red" in result
        assert "- Neckline: V-Neck" in result
        assert "Machine wash cold" not in result
        assert "100% Cotton" not in result
        assert "Trendy" not in result

    def test_only_flagged_attributes_included_ar(self) -> None:
        ar = {
            "name": "فستان",
            "attributes": [
                {"code": "primary_color", "name": "اللون", "value": "أحمر"},
                {"code": "dress_style", "name": "الستايل", "value": "كاجوال"},
                {"code": "care_instructions", "name": "العناية", "value": "غسيل بارد"},
            ],
        }
        result = self.fmt(ar, "ar")
        assert result is not None
        assert "الخصائص:" in result
        assert "- اللون: أحمر" in result
        assert "- الستايل: كاجوال" in result
        assert "غسيل بارد" not in result

    def test_boilerplate_removed(self) -> None:
        en = {
            "name": "Dress",
            "price": 99.99,
            "currency": "SAR",
            "sku": "DR-001",
            "brand": "Zara",
            "ai_description": "AI boilerplate",
            "care_instructions": "Wash cold",
            "long_description": "Long marketing copy",
            "collection": "Summer 2026",
            "country_of_origin": "CN",
            "images": [{"alt_text": "Front view"}],
            "sizes": [{"label": "M"}],
            "variants": [{"sku": "DR-RED-M", "options": ["Red"], "price": 99.99}],
        }
        result = self.fmt(en, "en")
        assert result is not None
        assert "Price tier: mid SAR" in result
        assert "SKU" not in result
        assert "Brand" not in result
        assert "AI boilerplate" not in result
        assert "Wash cold" not in result
        assert "Long marketing copy" not in result
        assert "Summer 2026" not in result
        assert "Country" not in result
        assert "Front view" not in result
        assert "Sizes" not in result
        assert "Variants" not in result

    def test_flagless_attributes_alone_yield_no_attributes_section(self) -> None:
        en = {"name": "Dress", "attributes": [{"code": "care_instructions", "name": "Care", "value": "Wash"}]}
        result = self.fmt(en, "en")
        assert result is not None
        assert "Attributes" not in result
        assert "Wash" not in result

    def test_short_description_boilerplate_stripped_before_embedding(self) -> None:
        en = {
            "name": "Dress",
            "short_description": "Model height: 178 cm\n\nZARA WOMAN COLLECTION\n\nElegant midi dress.",
        }
        result = self.fmt(en, "en")
        assert result is not None
        assert "Model height" not in result
        assert "ZARA WOMAN COLLECTION" not in result
        assert "Short Description: Elegant midi dress." in result

    def test_localized_enrichment_tokens_ar(self) -> None:
        ar = {
            "name": "فستان",
            "price": 150.0,
            "currency": "SAR",
            "short_description": "فستان صيفي لمناسبة حفلة",
        }
        result = self.fmt(ar, "ar")
        assert result is not None
        assert "فئة السعر: فاخر SAR" in result
        assert "الموسم: موسمي" in result
        assert "المناسبة: مناسبة حفلة" in result

    def test_enrichment_tokens_en(self) -> None:
        en = {
            "name": "Dress",
            "price": 10.0,
            "currency": "SAR",
            "short_description": "Party dress for summer nights",
        }
        result = self.fmt(en, "en")
        assert result is not None
        assert "Price tier: budget SAR" in result
        assert "Season: seasonal" in result
        assert "Occasion: party occasion" in result


class TestEmbedSingleProduct:
    @pytest_asyncio.fixture
    def ai_client(self) -> MagicMock:
        client = MagicMock(spec=AIEngineClient)
        client.embed_product = AsyncMock(return_value={"status": "ok"})
        return client

    async def _status(self, db_session: AsyncSession, pid: str) -> str | None:
        row = await db_session.execute(
            sa.select(ProductEmbedding.embedding_status).where(
                ProductEmbedding.product_id == pid,
                ProductEmbedding.model_name == DEFAULT_EMBEDDING_MODEL,
            )
        )
        return row.scalar_one_or_none()

    @pytest.mark.asyncio
    async def test_embeds_both_langs_and_marks_done(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
        ai_client: MagicMock,
    ) -> None:
        with patch(
            "app.services.embedding_cron.build_embed_data",
            new=AsyncMock(return_value=("text en", "text ar", {"en": {"name": "Dress"}}, {"_size": ["m"]})),
        ):
            ok = await _embed_single_product(db_session, {"id": "sp-stale-pending"}, ai_client)

        assert ok is True
        assert ai_client.embed_product.await_count == 2
        calls = ai_client.embed_product.await_args_list
        assert calls[0].args[1] == "en"
        assert calls[1].args[1] == "ar"
        assert calls[0].args[2] == "text en"
        assert calls[1].args[2] == "text ar"
        assert calls[0].kwargs["payload"] == {"en": {"name": "Dress"}}
        assert calls[1].kwargs["filters"] == {"_size": ["m"]}
        assert await self._status(db_session, "sp-stale-pending") == "done"

    @pytest.mark.asyncio
    async def test_marks_error_when_ar_call_fails(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
        ai_client: MagicMock,
    ) -> None:
        ai_client.embed_product = AsyncMock(side_effect=[{"status": "ok"}, {"status": "error"}])
        with patch(
            "app.services.embedding_cron.build_embed_data",
            new=AsyncMock(return_value=("text en", "text ar", {"en": {}}, {})),
        ):
            ok = await _embed_single_product(db_session, {"id": "sp-stale-pending"}, ai_client)

        assert ok is False
        assert ai_client.embed_product.await_count == 2
        assert await self._status(db_session, "sp-stale-pending") == "error"

    @pytest.mark.asyncio
    async def test_skips_missing_lang_text(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
        ai_client: MagicMock,
    ) -> None:
        with patch(
            "app.services.embedding_cron.build_embed_data",
            new=AsyncMock(return_value=("text en", None, {"en": {}}, {})),
        ):
            ok = await _embed_single_product(db_session, {"id": "sp-stale-pending"}, ai_client)

        assert ok is True
        assert ai_client.embed_product.await_count == 1
        assert ai_client.embed_product.await_args_list[0].args[1] == "en"
        assert await self._status(db_session, "sp-stale-pending") == "done"


class TestExtractGenderFilter:
    def test_recognizes_all_gender_attribute_codes(self) -> None:
        for code in (
            "target_customer",
            "gender",
            "gender_target",
            "watch_gender_target",
            "eyewear_gender_target",
        ):
            result = _extract_gender_filter([{"code": code, "value": "Women"}])
            assert result == ["women"]

    def test_normalizes_male_female_children_variants(self) -> None:
        assert _extract_gender_filter([{"code": "gender", "value": "Male"}]) == ["men"]
        assert _extract_gender_filter([{"code": "gender", "value": "Female"}]) == ["women"]
        assert _extract_gender_filter([{"code": "gender", "value": "Girls"}]) == ["girls"]
        assert _extract_gender_filter([{"code": "gender", "value": "Boys"}]) == ["boys"]
        assert _extract_gender_filter([{"code": "gender", "value": "Babies"}]) == ["babies"]
        assert _extract_gender_filter([{"code": "gender", "value": "Kids"}]) == ["kids"]

    def test_deduplicates_values(self) -> None:
        attrs = [
            {"code": "target_customer", "value": ["Women", "Girls", "women"]},
            {"code": "gender", "value": "Female"},
        ]
        result = _extract_gender_filter(attrs)
        assert sorted(result) == ["girls", "women"]

    def test_ignores_unrelated_attributes(self) -> None:
        attrs = [{"code": "color", "value": "Red"}, {"code": "material", "value": "Cotton"}]
        assert _extract_gender_filter(attrs) == ["unisex"]

    def test_defaults_to_unisex_when_missing(self) -> None:
        assert _extract_gender_filter([]) == ["unisex"]

    def test_ignores_empty_or_unknown_values(self) -> None:
        attrs = [{"code": "gender", "value": ""}, {"code": "gender", "value": "unknown-value"}]
        assert _extract_gender_filter(attrs) == ["unisex"]

    def test_handles_non_list_input(self) -> None:
        assert _extract_gender_filter(None) == ["unisex"]  # type: ignore[arg-type]


class TestNormalizeSizeTokens:
    def test_letter_sizes(self) -> None:
        assert _normalize_size_tokens("M") == ["m"]
        assert _normalize_size_tokens("XL") == ["xl"]
        assert _normalize_size_tokens("XXL") == ["xxl"]
        assert _normalize_size_tokens("XS") == ["xs"]

    def test_word_sizes_collapse_to_canonical(self) -> None:
        assert _normalize_size_tokens("Medium") == ["m", "medium"]
        assert _normalize_size_tokens("Extra Large") == ["xl", "extra large"]
        assert _normalize_size_tokens("extra small") == ["xs", "extra small"]

    def test_numeric_sizes(self) -> None:
        assert _normalize_size_tokens("42") == ["42"]
        assert _normalize_size_tokens("40.5") == ["40.5"]

    def test_numeric_sizes_with_system_tag(self) -> None:
        assert _normalize_size_tokens("42", "EU") == ["42", "eu:42"]
        assert _normalize_size_tokens("8.5", "US") == ["8.5", "us:8.5"]

    def test_system_prefixed_label(self) -> None:
        assert _normalize_size_tokens("EU 42") == ["42", "eu:42"]
        assert _normalize_size_tokens("US 8") == ["8", "us:8"]

    def test_one_size_variants(self) -> None:
        assert _normalize_size_tokens("One Size") == ["one size"]
        assert _normalize_size_tokens("OS") == ["one size", "os"]
        assert _normalize_size_tokens("Free Size") == ["one size", "free size"]

    def test_freeform_label_falls_back_to_raw(self) -> None:
        assert _normalize_size_tokens("Longline") == ["longline"]

    def test_unknown_system_keeps_raw_number_only(self) -> None:
        assert _normalize_size_tokens("42", "XX") == ["42"]

    def test_empty_label_returns_empty(self) -> None:
        assert _normalize_size_tokens("") == []
        assert _normalize_size_tokens("   ") == []


class TestBuildFlatFilters:
    def test_bilingual_category_chain_and_brand(self) -> None:
        en = {"category": {"name": "Dresses"}, "category_parents": [{"name": "Casual Dresses"}], "brand": "Zara"}
        ar = {"category": {"name": "فساتين"}, "category_parents": [{"name": "فساتين كاجوال"}], "brand": "زارا"}
        filters = _build_flat_filters(en, ar)
        assert sorted(filters["_category"]) == ["Casual Dresses", "Dresses", "فساتين", "فساتين كاجوال"]
        assert sorted(filters["_brand"]) == ["Zara", "زارا"]

    def test_category_single_level_without_parents(self) -> None:
        en = {"category": {"name": "Dresses"}}
        ar = {"category": {"name": "فساتين"}}
        filters = _build_flat_filters(en, ar)
        assert sorted(filters["_category"]) == ["Dresses", "فساتين"]

    def test_color_matched_by_code_in_arabic_info(self) -> None:
        ar = {
            "attributes": [
                {"code": "primary_color", "name": "اللون", "value": "أحمر"},
            ]
        }
        filters = _build_flat_filters({}, ar)
        assert filters["_color"] == ["أحمر"]

    def test_material_matched_by_code(self) -> None:
        en = {
            "attributes": [
                {"code": "main_material", "name": "Material", "value": ["Cotton", "Linen"]},
            ]
        }
        filters = _build_flat_filters(en, {})
        assert sorted(filters["_material"]) == ["Cotton", "Linen"]

    def test_bilingual_color_values_deduplicated(self) -> None:
        en = {"attributes": [{"code": "primary_color", "name": "Color", "value": "Red"}]}
        ar = {"attributes": [{"code": "primary_color", "name": "اللون", "value": "أحمر"}, {"code": "secondary_color", "name": "اللون الثانوي", "value": "Red"}]}
        filters = _build_flat_filters(en, ar)
        assert filters["_color"] == ["Red", "أحمر"]

    def test_gender_extracted_and_unisex_default(self) -> None:
        en = {"attributes": [{"code": "target_customer", "name": "Target Customer", "value": ["Women", "Girls"]}]}
        filters = _build_flat_filters(en, {})
        assert sorted(filters["_gender"]) == ["girls", "women"]

        assert _build_flat_filters({}, {})["_gender"] == ["unisex"]

    def test_empty_lists_removed(self) -> None:
        filters = _build_flat_filters({}, {})
        assert filters.keys() == {"_gender", "_size"}
        assert filters["_size"] == ["one size"]

    def test_printed_normalized_to_multicolor(self) -> None:
        en = {"attributes": [{"code": "primary_color", "name": "Color", "value": "Printed"}]}
        filters = _build_flat_filters(en, {})
        assert filters["_color"] == ["Multicolor"]

        ar = {"attributes": [{"code": "primary_color", "name": "اللون", "value": "مطبوع"}]}
        assert _build_flat_filters({}, ar)["_color"] == ["متعدد الألوان"]

    def test_case_insensitive_color_alias(self) -> None:
        en = {"attributes": [{"code": "primary_color", "name": "Color", "value": "printed"}]}
        filters = _build_flat_filters(en, {})
        assert filters["_color"] == ["Multicolor"]

    def test_sizes_added_from_product_sizes(self) -> None:
        en = {
            "sizes": [
                {"label": "M", "system": "US", "stock": 3},
                {"label": "40", "system": "EU", "stock": 2},
            ]
        }
        filters = _build_flat_filters(en, {})
        assert sorted(filters["_size"]) == ["40", "eu:40", "m"]

    def test_sizes_bilingual_merged_and_deduped(self) -> None:
        en = {"sizes": [{"label": "M", "system": "US", "stock": 1}]}
        ar = {"sizes": [{"label": "m", "system": "US", "stock": 1}, {"label": "L", "system": "US", "stock": 1}]}
        filters = _build_flat_filters(en, ar)
        assert filters["_size"] == ["m", "l"]

    def test_string_size_entries_accepted(self) -> None:
        filters = _build_flat_filters({"sizes": ["XL", "One Size"]}, {})
        assert sorted(filters["_size"]) == ["one size", "xl"]

    def test_no_sizes_falls_back_to_one_size(self) -> None:
        filters = _build_flat_filters({"name": "Dress"}, {})
        assert filters["_size"] == ["one size"]

    def test_sizes_present_not_overridden_by_fallback(self) -> None:
        filters = _build_flat_filters({"sizes": [{"label": "M", "system": "US"}]}, {})
        assert filters["_size"] == ["m"]


class TestExtractOptionUuids:
    def test_json_array(self) -> None:
        assert _extract_option_uuids('["878e89cb-0000-0000-0000-000000000001"]') == ["878e89cb-0000-0000-0000-000000000001"]

    def test_json_array_multiple(self) -> None:
        assert _extract_option_uuids('["878e89cb-0000-0000-0000-000000000001", "878e89cb-0000-0000-0000-000000000002"]') == [
            "878e89cb-0000-0000-0000-000000000001",
            "878e89cb-0000-0000-0000-000000000002",
        ]

    def test_bare_uuid(self) -> None:
        assert _extract_option_uuids("878e89cb-0000-0000-0000-000000000001") == ["878e89cb-0000-0000-0000-000000000001"]

    def test_non_uuid_text_ignored(self) -> None:
        assert _extract_option_uuids("Printed") == []

    def test_garbage_and_empty(self) -> None:
        assert _extract_option_uuids(None) == []  # type: ignore[arg-type]
        assert _extract_option_uuids("") == []
        assert _extract_option_uuids("not-json{") == []


class TestFetchProductColorData:
    @pytest.mark.asyncio
    async def test_unions_product_and_variant_colors(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
    ) -> None:
        await db_session.execute(
            sa.text("""
                INSERT INTO attribute_groups (id, code, name_en, name_ar, name_fa, sort_order)
                VALUES ('grp-color-test', 'color', 'Color', 'اللون', 'رنگ', 0)
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO attributes (id, group_id, code, name_en, name_ar, name_fa,
                            value_type, input_type, is_required, is_filterable, is_searchable,
                            is_visible_on_show, is_variant_defining, sort_order)
                VALUES ('attr-color-test', 'grp-color-test', 'primary_color', 'Color', 'اللون', 'رنگ',
                'option', 'select', false, true, true, true, false, 0)
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO attribute_options (id, attribute_id, code, value_en, value_ar, value_fa, is_major, sort_order)
                VALUES
                    ('11111111-1111-4111-8111-111111111101', 'attr-color-test', 'red', 'Red', 'أحمر', 'قرمز', false, 0),
                    ('11111111-1111-4111-8111-111111111102', 'attr-color-test', 'black', 'Black', 'أسود', 'مشکی', false, 1),
                    ('11111111-1111-4111-8111-111111111103', 'attr-color-test', 'printed', 'Printed', 'مطبوع', 'چاپی', false, 2),
                    ('11111111-1111-4111-8111-111111111104', 'attr-color-test', 'navy', 'Navy', 'كحلي', 'سرمهای', false, 3)
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO product_attribute_values (id, product_id, attribute_id, value)
                VALUES ('pav-printed-test', 'sp-stale-pending', 'attr-color-test', '["11111111-1111-4111-8111-111111111103"]')
                ON CONFLICT DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO product_variants (id, product_id, sku, price, quantity, low_stock_threshold, sort_order, is_active)
                VALUES
                    ('var-red-test', 'sp-stale-pending', 'SKU-RED', 10, 1, 5, 0, true),
                    ('var-black-test', 'sp-stale-pending', 'SKU-BLACK', 10, 1, 5, 0, true),
                    ('var-navy-test', 'sp-stale-pending', 'SKU-NAVY', 10, 1, 5, 0, false)
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO variant_attribute_options (variant_id, attribute_option_id)
                VALUES
                    ('var-red-test', '11111111-1111-4111-8111-111111111101'),
                    ('var-black-test', '11111111-1111-4111-8111-111111111102'),
                    ('var-navy-test', '11111111-1111-4111-8111-111111111104')
                ON CONFLICT DO NOTHING
            """)
        )
        await db_session.commit()

        colors, families = await _fetch_product_color_data(db_session, "sp-stale-pending")
        assert "Red" in colors
        assert "أحمر" in colors
        assert "Multicolor" in colors
        assert "أسود" in colors
        assert "Navy" not in colors
        assert "كحلي" not in colors

    @pytest.mark.asyncio
    async def test_resolves_families_and_printed_alias(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
    ) -> None:
        await db_session.execute(
            sa.text("""
                INSERT INTO attribute_groups (id, code, name_en, name_ar, name_fa, sort_order)
                VALUES ('grp-color-fam-test', 'color-fam', 'Color', 'اللون', 'رنگ', 0)
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO attributes (id, group_id, code, name_en, name_ar, name_fa,
                            value_type, input_type, is_required, is_filterable, is_searchable,
                            is_visible_on_show, is_variant_defining, sort_order)
                VALUES ('attr-color-fam-test', 'grp-color-fam-test', 'secondary_color', 'Secondary Color',
                'اللون الثانوي', 'رنگ ثانوی', 'option', 'select', false, true, true, true, false, 0)
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO attribute_options (id, attribute_id, code, value_en, value_ar, value_fa, is_major, color_family, sort_order)
                VALUES
                    ('22222222-2222-4222-8222-222222222201', 'attr-color-fam-test', 'red', 'Red', 'أحمر', 'قرمز', false, 'reds-pinks', 0),
                    ('22222222-2222-4222-8222-222222222202', 'attr-color-fam-test', 'printed', 'Printed', 'مطبوع', 'چاپی', false, NULL, 1)
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await db_session.execute(
            sa.text("""
                INSERT INTO product_attribute_values (id, product_id, attribute_id, value)
                VALUES ('pav-fam-test', 'sp-stale-pending', 'attr-color-fam-test', '["22222222-2222-4222-8222-222222222201", "22222222-2222-4222-8222-222222222202"]')
                ON CONFLICT DO NOTHING
            """)
        )
        await db_session.commit()

        colors, families = await _fetch_product_color_data(db_session, "sp-stale-pending")
        assert families == ["reds-pinks", "specialty"]
        assert "Multicolor" in colors


class TestFetchUnembeddedProducts:
    @pytest.mark.asyncio
    async def test_fetches_pending_and_generating(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
    ) -> None:
        results = await fetch_unembedded_products(db_session)
        ids = [r["id"] for r in results]
        assert "sp-stale-pending" in ids
        assert "sp-stale-generating" in ids

    @pytest.mark.asyncio
    async def test_includes_recent_products(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
    ) -> None:
        results = await fetch_unembedded_products(db_session)
        ids = [r["id"] for r in results]
        assert "sp-recent-pending" in ids

    @pytest.mark.asyncio
    async def test_excludes_done_by_default(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
    ) -> None:
        results = await fetch_unembedded_products(db_session)
        ids = [r["id"] for r in results]
        assert "sp-done" not in ids

    @pytest.mark.asyncio
    async def test_excludes_error_by_default(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
    ) -> None:
        results = await fetch_unembedded_products(db_session)
        ids = [r["id"] for r in results]
        assert "sp-error" not in ids

    @pytest.mark.asyncio
    async def test_includes_error_when_flag_set(
        self,
        db_session: AsyncSession,
        seed_embedding_products: None,
    ) -> None:
        results = await fetch_unembedded_products(db_session, include_errors=True)
        ids = [r["id"] for r in results]
        assert "sp-error" in ids
