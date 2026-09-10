# Product Definition System

## Overview

A fully dynamic, attribute-based product definition system supporting 30 product types across fashion, footwear, accessories, beauty, fragrance, and body care. Store owners use a multi-step form (stepper) to define products. The system is locale-aware (ar/en/fa) and AI-ready for RAG search.

## Implementation Status

| Phase | What                                                                  | Status   |
| ----- | --------------------------------------------------------------------- | -------- |
| 1     | Backend: Database tables, seed data, APIs                             | Complete |
| 2     | Backend: CRUD endpoints for products + attributes + variants + images | Complete |
| 3     | Frontend: Attribute-based dynamic form renderer                       | Complete |
| 4     | Frontend: Product image uploader with view type selection             | Complete |
| 5     | Frontend: Stepper with category/attribute/image/variant steps         | Complete |
| 6     | Backend: Embedding generation pipeline                                | Complete |
| 7     | Frontend: RAG search UI                                               | Complete |

## Key Design Decisions

| Decision                  | Choice                                                                |
| ------------------------- | --------------------------------------------------------------------- |
| Primary keys              | UUID (string), auto-generated in application code                     |
| Attribute options scope   | Per-attribute (not shared between attributes)                         |
| Attribute code uniqueness | Globally unique — shared codes renamed per domain                     |
| Value storage for selects | Option ID string                                                      |
| Locale support            | All names/values in ar/en/fa, stored in columns                       |
| Category→ProductType      | FK `categories.product_type_id`; auto-derived in form                 |
| Image view types          | Scoped to product type, inherited by all subcategories                |
| Size system               | Relational table (`product_sizes`) — display-only, no form step       |
| Form UI                   | Stepper, submit only on last step                                     |
| Form rendering            | Dynamic from attribute definitions + `input_type`                     |
| Variant generation        | Cartesian product computed client-side (`VariantGridEditor`)          |
| Multi-piece products      | Pieces + atomic color sets (`is_multi_piece`, `pieces`, `color_sets`) |

## Category System

- Categories form a tree via `parent_id`
- Each category has `product_type_id` FK linking to its product type
- The API returns a tree via `GET /api/v1/products/categories` (optionally filtered by `product_type_id`)
- On the frontend, the product form fetches the category tree unconditionally

### Product Type Auto-Derivation

The product type is NOT selected manually by the user. Instead:

1. User selects a category in BasicInfoStep
2. Frontend builds `categoryPtMap` from the category tree: `Map<categoryId, productTypeId>`
3. `effectiveProductTypeId` is derived as: `categoryPtMap[formValues.category_id]`
4. This value drives which attribute groups and attributes are shown
5. In edit mode, `initialData.product_type_id` is used as fallback if the category tree hasn't loaded yet

```typescript
// ProductForm.tsx — simplified
const { data: allCategories = [] } = useGetCategoryTreeQuery({});

const categoryPtMap = useMemo(() => {
  const map: Record<string, string> = {};
  const walk = (nodes: CategoryNode[]) => {
    for (const node of nodes) {
      if (node.product_type_id) map[node.id] = node.product_type_id;
      walk(node.children);
    }
  };
  walk(allCategories);
  return map;
}, [allCategories]);

const effectiveProductTypeId = useMemo(() => {
  if (categoryId && categoryPtMap[categoryId]) return categoryPtMap[categoryId];
  return initialData?.product_type_id || "";
}, [categoryId, categoryPtMap, initialData]);
```

## Attribute System

### Groups

Attribute groups map to stepper steps. Each product type gets only the groups that have attributes linked to it:

| Group Code        | Name              | Example Types Using It          |
| ----------------- | ----------------- | ------------------------------- |
| colors-pattern    | Colors & Patterns | All fashion types               |
| materials         | Materials         | All fashion types               |
| style-occasion    | Style & Occasion  | Garments, shoes                 |
| fit-size          | Fit & Size        | Garments                        |
| features-tags     | Features & Tags   | All fashion types               |
| dress-specs       | Dress Specs       | Dresses                         |
| shoe-details      | Shoe Details      | Athletic, boots, heels, sandals |
| shoe-materials    | Shoe Materials    | All shoe types                  |
| shoe-features     | Shoe Features     | All shoe types                  |
| bag-style         | Bag Style         | Bags                            |
| bag-sizing        | Bag Sizing        | Bags                            |
| jewelry-specs     | Jewelry Specs     | All jewelry types               |
| fragrance-specs   | Fragrance Specs   | Fragrance                       |
| heels-dress-specs | Heels Specs       | Heels                           |
| …                 | 30+ groups total  | …                               |

### Attribute Code Uniqueness

Attribute `code` is globally unique across ALL product types. When the same conceptual attribute needs different options or belongs to different groups for different product types, codes are renamed.

Example — `closure_type` is split into:

- `shoe_closure_type` (for all shoe types)
- `bag_closure_type` (for bags)
- `top_closure_type` (for tops)
- `skirt_closure_type` (for skirts)
- `outerwear_closure_type` (for outerwear)
- `closure_type` (kept for dresses only)

### Dynamic Form Rendering

Each attribute renders based on its `input_type` (dispatched in `AttributeFieldRenderer`):

| input_type     | Component                                       | Stored value                                |
| -------------- | ----------------------------------------------- | ------------------------------------------- |
| `select`       | `SingleSelect` dropdown                         | Option ID                                   |
| `multi-select` | Searchable `MultiSelect` dialog with Apply      | JSON array of option IDs                    |
| `color-picker` | `ColorPicker` — swatch dialog grouped by family | Option ID                                   |
| `text`         | `<Input>`                                       | String                                      |
| `textarea`     | `<Textarea>`                                    | String                                      |
| `number`       | `<Input type="number">`                         | Numeric string                              |
| `switch`       | Toggle switch                                   | `"true"` / `"false"`                        |
| `composition`  | `CompositionInput` — material + % sliders       | Material or `[{material, percentage}]` JSON |

### Validation Rules Engine

Each attribute can carry `validation_rules` with trilingual (ar/en/fa) messages. `buildRules` in `AttributeFieldRenderer` translates them into react-hook-form rules:

| Rule         | Mapped to                               |
| ------------ | --------------------------------------- |
| `required`   | `required`                              |
| `min_length` | `minLength`                             |
| `max_length` | `maxLength`                             |
| `min`        | `min`                                   |
| `max`        | `max`                                   |
| `pattern`    | regex check via `validate`              |
| `min_select` | array-length check on multi-select JSON |
| `max_select` | array-length check on multi-select JSON |

### Long Option Lists

The Show More / Less cutoff (threshold 15) lives in the Catalog Data browser (`CategoryAttributeTree.SHOW_MORE_THRESHOLD`) — NOT in the product form. Form widgets handle large option lists differently: `ColorPicker` opens a dialog whose swatches are grouped by `color_family`, and `MultiSelect` shows a search box above 5 options and groups by color family when any option has one.

## Product Form Stepper

Steps are built dynamically (`allSteps` in `ProductForm.tsx`); the indicator shows a sliding window of 3 steps. There is no Sizes step — sizes are display-only (`product_sizes` rendered in the product view).

| Step          | What's Rendered                                                                                                                                        | Source                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| 1 Basic Info  | name_en\*, brand\*, category\* (tree select), source_url (URL-validated, read-only in edit mode), collection en/ar, multi-piece toggle + pieces editor | `BasicInfoStep`                            |
| 2 Description | short_description_en\* (min 20 chars), short_description_ar, long descriptions en/ar                                                                   | `DescriptionStep`                          |
| 3..n          | Attribute groups — one step per group that has attributes for the effective product type, ordered by `sort_order`                                      | `AttributesStep`                           |
| n+1           | Pricing & Inventory — price\* (> 0), original_price, quantity + inline variant grid                                                                    | `PriceInventoryStep` + `VariantGridEditor` |
| n+2           | Media — image uploader with view types, variant binding, alt text                                                                                      | `MediaStep` + `ProductImageUploader`       |
| Last          | Review & Submit — counts summary                                                                                                                       | `ReviewStep`                               |

Per-step gating (`validateStep`): basic info requires an effective product type; the description step requires `short_description_en`; attribute steps trigger each attribute's validation rules; multi-piece products must have at least one complete color set; the pricing step requires price plus at least one active variant with SKU; the media step requires ≥ 3 images, each with a view type and English alt text. Submit is only enabled on the last step.

### Key Components

- **ProductForm.tsx** — Root form orchestrator: stepper state, `categoryPtMap`/`effectiveProductTypeId`, images/variants/pieces/colorSets state, per-step validation, submit + redirect
- **steps/BasicInfoStep.tsx** — Category selector (no product type select), name/brand/category fields, multi-piece toggle + pieces editor
- **steps/DescriptionStep.tsx** — Short/long descriptions in en/ar
- **steps/AttributesStep.tsx** — Renders `AttributeFieldRenderer` for the current group
- **steps/CompositeColorSetsEditor.tsx** — Multi-piece color-set rows (replaces the colors-pattern attribute step)
- **AttributeFieldRenderer.tsx** — Input-type dispatch + `validation_rules` engine
- **CompositionInput.tsx** — Composition input: one material, or two materials with percentage sliders summing to 100
- **VariantGridEditor.tsx** — Client-side variant generation/editing grid (hosted inside `PriceInventoryStep`)
- **steps/PriceInventoryStep.tsx** — Price, sale/original price, inventory + `VariantGridEditor`
- **steps/MediaStep.tsx** — Hosts `ProductImageUploader`
- **ProductImageUploader.tsx** — Immediate upload, crop-and-reupload, view type + variant binding + alt text per image
- **steps/ReviewStep.tsx** — Summary counts before submission

## Frontend Data Flow

```
ProductForm.tsx
  ├── useGetCategoryTreeQuery({})           → category tree (unconditional)
  ├── useGetStoreQuery(storeId)             → store (currency symbol)
  ├── useProductFormData(effectiveProductTypeId)
  │     ├── useGetProductTypesQuery()             → product types list (display only)
  │     ├── useGetAttributeGroupsQuery()          → ALL attribute groups (takes no args)
  │     ├── useGetCategoryTreeQuery({})           → category tree
  │     ├── useGetProductTypeAttributesQuery(     → attributes for the type
  │     │     { product_type_id })
  │     ├── useGetImageViewTypesQuery(product_type_id) → scoped image view types
  │     ├── useGetBrandsQuery()                   → brands
  │     └── useCreateStoreProductMutation /
  │         useUpdateStoreProductMutation         → submit
  └── buildProductPayload()                 → everything sent inline in ONE request
```

Groups with no attributes for the effective product type are filtered out before mapping to steps (`activeAttrGroups`).

## Multi-Piece Products

Toggled in BasicInfoStep (`is_multi_piece`). A multi-piece product (e.g. abaya + scarf) defines named **pieces** and atomic **color sets**:

1. **Pieces editor** (in `BasicInfoStep`) — add/remove pieces, each with a name
2. **Color sets** — while multi-piece, the first attribute step (the `colors-pattern` group slot) renders `CompositeColorSetsEditor` instead of regular attributes. Each row is an atomic combination: every piece gets one color chosen from the pooled color options (`options` with `color_hex` across all attributes). Customers can only buy colors within the same row.
3. **Validation** (`validateColorSetsStep`) — at least one color set must exist, and every piece in every set must have a color assigned
4. **Variants** — `primary_color` is excluded from variant-defining attributes; instead each variant can bind to a color set (`color_set_id`), and the grid crosses every color set with the remaining attribute combinations
5. **Payload** (`buildProductPayload` in `lib/product-form.ts`) — sends `is_multi_piece`, `pieces[]` (`name_en`/`name_ar`/`sort_order`) and `color_sets[]` (`sort_order`, `values[{piece_id, color_option_id}]`) inline

IDs vs indexes: within the form, pieces and color sets are identified by their index (`sort_order`). On edit, `ProductForm` maps persisted IDs back to indexes (`pieceIdToIdx`/`csIdToIdx`) so the editors work with stable indexes; on submit, `colorSetIdxToId` remaps variant `color_set_id` values back to persisted color-set IDs.

## Variant Generation

- Variant-defining attributes are marked with `is_variant_defining = true`
- Variants are generated **client-side**: `VariantGridEditor` computes the cartesian product of selected options in a `useMemo` (recursive `cartesianAttr`), producing one row per combination
- For multi-piece products, every color set is crossed with the attribute combinations
- Row identity ("signature") = sorted comma-joined option IDs, prefixed `cs_<index>` when bound to a color set — variants are deduplicated by this signature
- An effect auto-adds rows for new combinations as options change; existing variants are never dropped client-side (uncovered ones keep rendering below the generated rows)
- Each row: active toggle, SKU (required when active), quantity (defaults to the form quantity), optional custom price — when null, `buildVariantPayload` falls back to the product-level price
- Validation: if any variants exist, at least one must be active; active variants require a SKU
- On submit, the full variants array is sent inline in the create/update body — the backend replaces variants from the payload. There are NO per-variant endpoints.

## Image Upload

There is NO temp-files→move pattern and NO dedicated image endpoints. Files go up immediately:

1. Files picked via file picker → each becomes an `ImageUploadItem` with a temporary `blob:` preview and `uploading: true`
2. Each file uploads right away via `POST /files/upload` (`useUploadFileMutation` in `fileApi`, multipart); the preview URL is swapped for the returned server URL (per-item error state on failure)
3. Crop-and-reupload: `ImageCropDialog` (react-image-crop → canvas → JPEG blob) re-uploads the cropped file and swaps the URL

Per image the uploader collects:

- View type — `SingleSelect` over view types scoped to the product type (`product_type_image_view_types`)
- Variant binding — optional `SingleSelect` over variant signatures (stored as a sorted option-ID array, `variant_signature`)
- Alt text — `alt_text_en` / `alt_text_ar` (plus `alt_text_fa` kept in state)

Media-step rule (`validateMediaStep`): minimum **3 images**, each with a view type AND non-empty English alt text.

At submit, `buildImagePayload` puts all images (with `sort_order` for ordering) INLINE into the create/update body.

## Post-Submit: AI Description Generation

After a successful create/update, `ProductForm` redirects to `/seller/stores/{storeId}/products/{productId}/generate-description` (skipped when the form is embedded with an `onSuccess` callback, e.g. in dialogs).

The generate-description page:

- Auto-generates on entry — if the product has no AI description versions yet, it calls `POST /stores/{id}/products/{pid}/generate-descriptions` immediately (full-screen loading state)
- Header actions: **Show Prompt** (collapsible prompt panel), **History**, **Regenerate**
- Prompt panel: model selector limited to models with active API keys (`useGetLLMModelsQuery` filtered client-side), editable prompt `Textarea`, and an emerald **Run Edited Prompt** button that resubmits with the edited prompt
- Body: editable EN + AR description textareas, **Save Changes** (`PUT` with `ai_description_en/ar`) and **Next** (→ seller products)
- Error state: **Retry** / **Skip** buttons
- History dialog: past versions (date + model) with per-version **Restore**

## Key API Endpoints Used by Frontend

| Method | Endpoint                                      | Hook                                   |
| ------ | --------------------------------------------- | -------------------------------------- |
| GET    | `/products/types`                             | `useGetProductTypesQuery`              |
| GET    | `/products/categories`                        | `useGetCategoryTreeQuery`              |
| GET    | `/products/attribute-groups`                  | `useGetAttributeGroupsQuery` (no args) |
| GET    | `/products/attributes?product_type_id=`       | `useGetProductTypeAttributesQuery`     |
| GET    | `/products/image-view-types?product_type_id=` | `useGetImageViewTypesQuery`            |
| GET    | `/products/brands`                            | `useGetBrandsQuery`                    |
| POST   | `/files/upload`                               | `useUploadFileMutation` (fileApi)      |
| POST   | `/stores/{id}/products`                       | `useCreateStoreProductMutation`        |
| PUT    | `/stores/{id}/products/{pid}`                 | `useUpdateStoreProductMutation`        |

One request carries everything: basic fields, `attribute_values[]`, `variants[]`, `images[]`, and (multi-piece) `pieces[]` + `color_sets[]`.
