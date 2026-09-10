# Product Definition System

## Overview

A fully dynamic, attribute-based product definition system supporting 30 product types across fashion, footwear, accessories, beauty, and more. Store owners use a multi-step form to define products. The system is locale-aware (ar/en/fa) and AI-ready for RAG search.

## Database Schema

### Core Tables

```sql
product_types (
  id              UUID PRIMARY KEY,
  code            VARCHAR UNIQUE,     -- 'dresses', 'bags', 'boots', ...
  name_ar         TEXT,
  name_en         TEXT,
  name_fa         TEXT,
  icon            VARCHAR,            -- react-icon name, e.g. 'GiDress'
  sort_order      INTEGER
);

categories (
  id              UUID PRIMARY KEY,
  parent_id       UUID REFERENCES categories(id),
  product_type_id UUID REFERENCES product_types(id),
  code            VARCHAR,
  name_ar         TEXT,
  name_en         TEXT,
  name_fa         TEXT,
  icon            VARCHAR,
  sort_order      INTEGER,
  is_active       BOOLEAN DEFAULT true
);

store_products (
  id              UUID PRIMARY KEY,
  store_id        UUID REFERENCES stores(id) NOT NULL,
  product_type_id UUID REFERENCES product_types(id) NOT NULL,
  category_id     UUID REFERENCES categories(id),
  name_ar         TEXT, name_en         TEXT, name_fa         TEXT,
  brand           VARCHAR,
  sku             VARCHAR,
  status          VARCHAR DEFAULT 'draft',
  price           DECIMAL(10,2),
  has_variants    BOOLEAN DEFAULT false,
  ...
);
```

### Attribute System (EAV)

```sql
attribute_groups (
  id            UUID PRIMARY KEY,
  code          VARCHAR UNIQUE,     -- 'colors-pattern', 'materials', 'dress-specs', ...
  name_ar       TEXT, name_en       TEXT, name_fa       TEXT,
  icon          VARCHAR,
  sort_order    INTEGER
);

attributes (
  id                  UUID PRIMARY KEY,
  group_id            UUID REFERENCES attribute_groups(id),
  code                VARCHAR UNIQUE,     -- globally unique across ALL product types
  name_ar             TEXT, name_en       TEXT, name_fa       TEXT,
  description_ar      TEXT, description_en TEXT, description_fa TEXT,
  value_type          VARCHAR,            -- 'text', 'number', 'boolean', 'select', 'multiselect', 'color'
  input_type          VARCHAR,            -- 'text', 'textarea', 'number', 'switch', 'select', 'multi-select', 'color-picker'
  icon                VARCHAR,
  unit                VARCHAR,
  is_required         BOOLEAN DEFAULT false,
  is_variant_defining BOOLEAN DEFAULT false,
  is_filterable       BOOLEAN DEFAULT true,
  is_searchable       BOOLEAN DEFAULT true,
  is_search_affecting BOOLEAN DEFAULT false NOT NULL,
  is_visible_on_show  BOOLEAN DEFAULT true,
  validation_rules    JSONB,
  sort_order          INTEGER
);

attribute_options (
  id            UUID PRIMARY KEY,
  attribute_id  UUID REFERENCES attributes(id),
  code          VARCHAR,
  value_ar      TEXT, value_en      TEXT, value_fa      TEXT,
  icon          VARCHAR,
  color_hex     VARCHAR(7),
  image_url     VARCHAR(500),
  color_family  VARCHAR(50),
  is_major      BOOLEAN DEFAULT false,
  sort_order    INTEGER
);

product_type_attributes (
  product_type_id UUID REFERENCES product_types(id),
  attribute_id    UUID REFERENCES attributes(id),
  sort_order      INTEGER,
  PRIMARY KEY (product_type_id, attribute_id)
);
```

### Image & Variant System

```sql
product_type_image_view_types (
  id              UUID PRIMARY KEY,
  product_type_id UUID REFERENCES product_types(id),
  code            VARCHAR,
  name_ar         TEXT, name_en         TEXT, name_fa         TEXT,
  is_video        BOOLEAN DEFAULT false,
  sort_order      INTEGER
);

product_images (
  id            UUID PRIMARY KEY,
  product_id    UUID REFERENCES store_products(id) ON DELETE CASCADE,
  variant_id    UUID REFERENCES product_variants(id),
  view_type_id  UUID REFERENCES product_type_image_view_types(id),
  image_url     TEXT,
  sort_order    INTEGER,
  ...
);

product_variants (
  id              UUID PRIMARY KEY,
  product_id      UUID REFERENCES store_products(id) ON DELETE CASCADE,
  color_set_id    UUID REFERENCES product_color_sets(id),
  sku             VARCHAR,
  price           DECIMAL(10,2),
  quantity        INTEGER DEFAULT 0,
  is_active       BOOLEAN DEFAULT true,
  ...
);
```

## Product Types (30 Active)

| Sort | Code | Name |
|------|------|------|
| 1 | athletic_sneakers | Athletic & Sneakers |
| 2 | bags | Bags |
| 3 | boots | Boots |
| 4 | beauty | Beauty |
| 5 | heels_dress_shoes | Heels & Dress Shoes |
| 6 | belts_leather_goods | Belts & Leather Goods |
| 7 | sandals_slippers | Sandals & Slippers |
| 8 | head_accessories | Head Accessories |
| 9 | textile_accessories | Textile Accessories |
| 10 | specialty_accessories | Specialty Accessories |
| 11-14 | necklaces_pendants, bracelets_anklets, earrings, rings | Jewelry |
| 15 | other_jewelry | Other Jewelry |
| 16 | dresses | Dresses |
| 17 | tops | Tops |
| 18 | bottoms | Bottoms |
| 19 | outerwear | Outerwear |
| 20 | activewear | Activewear |
| 21 | swimwear | Swimwear |
| 22 | lingerie_sleepwear | Lingerie & Sleepwear |
| 23 | abayas | Abayas |
| 24 | scarves_hijabs | Scarves & Hijabs |
| 25 | fragrance | Fragrance & Perfume |
| 26 | watches | Watches |
| 27 | eyewear | Sunglasses & Eyewear |
| 28 | skirts | Skirts |
| 29 | suits_formalwear | Suits & Formalwear |
| 30 | body_care | Body Care |

Stale types (fashion, accessories, footwear) have been removed.

## Category System

- Categories form a tree structure via `parent_id`
- Each category has a `product_type_id` FK, linking it to a product type
- The category tree can be filtered by `product_type_id` or return all categories
- Product type is auto-derived from the selected category in the product form (frontend maps `category_id → category.product_type_id`)

## Attribute Code Uniqueness Strategy

**Principle**: Attribute `code` is globally unique across all product types.

- When the same conceptual attribute (e.g., `closure_type`) needs different options or belongs to different groups in different product types, the codes MUST be renamed (e.g., `shoe_closure_type`, `bag_closure_type`, `top_closure_type`)
- The seed script uses a `global_attr_map` dict keyed by code — first-file-wins for creating the attribute, subsequent files skip if the code already exists
- During the Feb 2026 migration, 97 attribute codes were renamed across 29 JSON files to eliminate group_code conflicts

**Resolution approach**: Renaming is preferred over normalizing groups because options, input types, and semantics differ per domain (e.g., shoe closures vs dress closures).

## Search-Affecting Attributes (`is_search_affecting`)

Every attribute carries an `is_search_affecting` boolean (column added by migration `a7f3e1d9c2b4`). It is the global switch that decides whether an attribute's values are written into the **embedding text** — i.e. whether the attribute participates in vector search similarity at all.

- **Canonical mapping**: `scripts/seed_data/search_affecting_flags.json` — a flat `{attribute_code: true|false}` map maintained by hand
- **Application**: `_apply_search_affecting_flags()` in `scripts/seed_product_definitions.py` runs on every seed (`make seed`) and bulk-updates `attributes.is_search_affecting` from that file — idempotent, keeps fresh and existing databases in sync with the canonical mapping
- **Consumption**:
  - Embedding text building (`app/services/embedding_cron.py`) resolves the flagged code set once per run (`_get_search_affecting_codes()`) and only attributes in that set are rendered into the per-language embed passage (`_format_embed_text()` → `_format_flagged_attrs()`). Unflagged attributes never reach the vector text.
  - The admin search-eval query generator builds its bilingual catalog context from product types + `is_search_affecting` attributes (+ major option values) before calling the AI Engine — see [docs/search-eval.md](search-eval.md)

To make a new attribute searchable through embeddings: add its code to `search_affecting_flags.json` with `true`, then re-run `make seed`. Changing flags only affects future embedding runs — already-embedded products need a re-index (`POST /admin/cron/embedding-products/reindex`) to pick up the new text.

## Seed Data Structure

```
scripts/seed_data/
├── 01_product_types.json              — 30 product types
├── 02_attribute_groups.json           — Attribute groups
├── 03_categories.json                 — Category tree with product_type_id
├── 04_image_view_types.json           — Image view types per product type
├── 05_attributes_fashion.json         — Shared fashion attributes (color, pattern, material, etc.)
├── 05_brands.json                     — Brand catalog
├── 06_countries.json                  — Countries
├── 07_currencies.json                 — Currencies
├── 08_attributes_bags.json            — Bag-specific attributes
├── 09_attributes_beauty.json          — Beauty-specific attributes
├── 11_attributes_belts_leather_goods.json
├── 12-14_attributes_head/textile/specialty_accessories.json
├── 15-18_attributes_athletic/boots/heels/sandals.json
├── 19-23_attributes_jewelry*.json     — 5 jewelry types
├── 24-32_attributes_dresses_to_scarves.json   — Garment types
├── 33_attributes_fragrance.json
├── 34_attributes_watches.json
├── 35_attributes_eyewear.json
├── 36_attributes_skirts.json
├── 37_attributes_suits_formalwear.json
├── 38_attributes_body_care.json
├── search_affecting_flags.json        — Canonical is_search_affecting map (see above)
├── search_eval_golden.json            — Search-eval golden set draft (imported via /admin/search-eval)
├── sitemap-category-kw-ar.xml         — Zara KW category sitemap (scraper reference)
└── zara_kw_categories.txt             — Zara KW category URLs (legacy crawler input)
```

Each file contains locale-aware attribute definitions with options:
```json
{
  "code": "sleeve_style",
  "name_ar": "نمط الكم",
  "name_en": "Sleeve Style",
  "name_fa": "سبک آستین",
  "value_type": "select",
  "input_type": "select",
  "group_code": "fit-size",
  "options": [
    { "code": "long", "value_ar": "طويل", "value_en": "Long", "value_fa": "بلند" }
  ]
}
```

## API Endpoints

### Public (no auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/products/types` | List all product types |
| GET | `/api/v1/products/types/{id}` | Product type detail with attributes |
| GET | `/api/v1/products/categories` | Category tree (filter by `product_type_id` or get all) |
| GET | `/api/v1/products/attribute-groups` | Attribute groups (filter by `product_type_id`) |
| GET | `/api/v1/products/attributes` | Attributes for a product type + group |
| GET | `/api/v1/products/attributes/{id}/options` | Attribute options |
| GET | `/api/v1/products/image-view-types` | Image view types for a product type |
| GET | `/api/v1/products/brands` | List brands |
| GET | `/api/v1/products/variant-combinations` | Generate variant combinations (cartesian product) |

### Authenticated (store owner)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/stores/{id}/products` | List store products |
| POST | `/api/v1/stores/{id}/products` | Create product (with variants, images, color sets) |
| GET | `/api/v1/stores/{id}/products/{pid}` | Get product detail |
| PUT | `/api/v1/stores/{id}/products/{pid}` | Update product (merge variants, replace images) |
| DELETE | `/api/v1/stores/{id}/products/{pid}` | Delete product |
| POST | `/api/v1/stores/{id}/products/{pid}/images` | Add image |
| PATCH | `/api/v1/stores/{id}/products/images/{iid}` | Update image |
| DELETE | `/api/v1/stores/{id}/products/images/{iid}` | Delete image |
| PUT | `/api/v1/stores/{id}/products/images/reorder` | Reorder images |
| PATCH | `/api/v1/stores/{id}/products/{pid}/variants/{vid}` | Update variant |
| DELETE | `/api/v1/stores/{id}/products/{pid}/variants/{vid}` | Delete variant |

## Seeding & Migrations

```bash
make seed              # Seed all product definitions (idempotent)
make migrate           # Apply pending Alembic migrations
make migration message="desc"   # Generate new migration
```

The seed script is idempotent — it creates product types, categories, attribute groups, attributes, and options. Attributes are created only if they don't already exist (keyed by code). Product-type-to-attribute links are always refreshed.

## Frontend Integration

- **Category tree** fetched unconditionally on the product form page
- **Product type** auto-derived from selected category's `product_type_id`
- **Attribute groups** rendered as stepper steps, each step contains a dynamic form based on `input_type`
- **Image upload** with view type selection per image
- **Variants** generated as cartesian product of variant-defining attribute options
