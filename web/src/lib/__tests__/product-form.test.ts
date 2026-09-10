import { describe, it, expect } from "vitest";
import {
  buildBasicPayload,
  buildAttributeValues,
  buildVariantPayload,
  buildImagePayload,
  buildProductPayload,
} from "../product-form";
import type { AttributeItem, AttributeOptionItem, ProductVariantInput } from "@/types/api";

describe("buildBasicPayload", () => {
  it("returns payload with provided fields", () => {
    const result = buildBasicPayload(
      { name_en: "Test", brand: "Nike", price: "99.99", quantity: "10", category_id: "cat1" },
      "type1",
    );
    expect(result.product_type_id).toBe("type1");
    expect(result.status).toBe("active");
    expect(result.name_en).toBe("Test");
    expect(result.brand).toBe("Nike");
    expect(result.price).toBe(99.99);
    expect(result.quantity).toBe(10);
    expect(result.category_id).toBe("cat1");
  });

  it("falls back name_fa to name_en when not provided", () => {
    const result = buildBasicPayload({ name_en: "Test" }, "type1");
    expect(result.name_fa).toBe("Test");
  });

  it("sets null for empty optional fields", () => {
    const result = buildBasicPayload({ name_en: "Test" }, "type1");
    expect(result.brand).toBeNull();
    expect(result.price).toBeNull();
    expect(result.quantity).toBe(0);
  });

  it("converts numeric fields from strings", () => {
    const result = buildBasicPayload(
      { name_en: "P", price: "50.5", original_price: "70", quantity: "3" },
      "t1",
    );
    expect(result.price).toBe(50.5);
    expect(result.original_price).toBe(70);
    expect(result.quantity).toBe(3);
  });
});

describe("buildAttributeValues", () => {
  const attributes: AttributeItem[] = [
    {
      id: "a1",
      group_id: "g1",
      code: "color",
      name_ar: "لون",
      name_en: "Color",
      name_fa: "رنگ",
      description_ar: null,
      description_en: null,
      description_fa: null,
      value_type: "string",
      input_type: "select",
      icon: null,
      unit: null,
      is_required: false,
      is_filterable: false,
      is_searchable: false,
      is_search_affecting: false,
      is_visible_on_show: false,
      is_variant_defining: false,
      sort_order: 0,
      options: [] as AttributeOptionItem[],
      validation_rules: null,
    },
    {
      id: "a2",
      group_id: "g1",
      code: "size",
      name_ar: "مقاس",
      name_en: "Size",
      name_fa: "سایز",
      description_ar: null,
      description_en: null,
      description_fa: null,
      value_type: "string",
      input_type: "select",
      icon: null,
      unit: null,
      is_required: false,
      is_filterable: false,
      is_searchable: false,
      is_search_affecting: false,
      is_visible_on_show: false,
      is_variant_defining: false,
      sort_order: 0,
      options: [] as AttributeOptionItem[],
      validation_rules: null,
    },
  ];

  it("returns values for attributes present in data", () => {
    const data = { attr_a1: "Red", attr_a2: "M" };
    const result = buildAttributeValues(data, attributes);
    expect(result).toEqual([
      { attribute_id: "a1", value: "Red" },
      { attribute_id: "a2", value: "M" },
    ]);
  });

  it("skips attributes with empty values", () => {
    const data = { attr_a1: "", attr_a2: "M" };
    const result = buildAttributeValues(data, attributes);
    expect(result).toEqual([{ attribute_id: "a2", value: "M" }]);
  });

  it("returns empty array when no data matches", () => {
    const data = { attr_other: "val" };
    const result = buildAttributeValues(data, attributes);
    expect(result).toEqual([]);
  });
});

describe("buildVariantPayload", () => {
  it("fills null price from productPrice when variant is active", () => {
    const variants: ProductVariantInput[] = [
      { sku: "V1", price: null, is_active: true } as ProductVariantInput,
    ];
    const result = buildVariantPayload(variants, 100);
    expect(result[0]!.price).toBe(100);
  });

  it("keeps existing price when variant has price", () => {
    const variants: ProductVariantInput[] = [
      { sku: "V1", price: 50, is_active: true } as ProductVariantInput,
    ];
    const result = buildVariantPayload(variants, 100);
    expect(result[0]!.price).toBe(50);
  });

  it("keeps null price when variant is inactive", () => {
    const variants: ProductVariantInput[] = [
      { sku: "V1", price: null, is_active: false } as ProductVariantInput,
    ];
    const result = buildVariantPayload(variants, 100);
    expect(result[0]!.price).toBeNull();
  });
});

describe("buildImagePayload", () => {
  it("maps image fields correctly", () => {
    const images = [
      {
        image_url: "https://example.com/img.jpg",
        view_type_id: "vt1",
        variant_signature: ["red", "M"],
        alt_text_ar: "وصف",
        alt_text_en: "desc",
        alt_text_fa: "توضیح",
        sort_order: 1,
      },
    ];
    const result = buildImagePayload(images);
    expect(result[0]).toEqual({
      image_url: "https://example.com/img.jpg",
      view_type_id: "vt1",
      variant_signature: ["red", "M"],
      alt_text_ar: "وصف",
      alt_text_en: "desc",
      alt_text_fa: "توضیح",
      sort_order: 1,
    });
  });

  it("sets null for missing alt texts", () => {
    const images = [
      {
        image_url: "https://example.com/img.jpg",
        view_type_id: null,
        variant_signature: null,
        alt_text_ar: "",
        alt_text_en: "",
        alt_text_fa: "",
        sort_order: 0,
      },
    ];
    const result = buildImagePayload(images);
    expect(result[0]!.alt_text_ar).toBeNull();
    expect(result[0]!.alt_text_en).toBeNull();
    expect(result[0]!.alt_text_fa).toBeNull();
  });
});

describe("buildProductPayload", () => {
  it("returns basic payload when no extras provided", () => {
    const result = buildProductPayload({ name_en: "Test" }, "type1", [], [], []);
    expect(result.name_en).toBe("Test");
    expect(result.product_type_id).toBe("type1");
  });

  it("includes attribute_values when present", () => {
    const attributes: AttributeItem[] = [
      {
        id: "a1",
        group_id: "g1",
        code: "color",
        name_ar: "لون",
        name_en: "Color",
        name_fa: "رنگ",
        description_ar: null,
        description_en: null,
        description_fa: null,
        value_type: "string",
        input_type: "select",
        icon: null,
        unit: null,
        is_required: false,
        is_filterable: false,
        is_searchable: false,
        is_search_affecting: false,
        is_visible_on_show: false,
        is_variant_defining: false,
        sort_order: 0,
        options: [] as AttributeOptionItem[],
        validation_rules: null,
      },
    ];
    const result = buildProductPayload({ name_en: "P", attr_a1: "Red" }, "t1", [], [], attributes);
    expect(result.attribute_values).toEqual([{ attribute_id: "a1", value: "Red" }]);
  });

  it("includes variants when present", () => {
    const variants: ProductVariantInput[] = [
      { sku: "V1", price: 20, is_active: true } as ProductVariantInput,
    ];
    const result = buildProductPayload({ name_en: "P" }, "t1", variants, [], []);
    expect(result.variants).toEqual(variants);
  });

  it("includes images when present", () => {
    const images = [
      {
        image_url: "https://img.com/a.jpg",
        view_type_id: null,
        variant_signature: null,
        alt_text_ar: "",
        alt_text_en: "",
        alt_text_fa: "",
        sort_order: 0,
      },
    ];
    const result = buildProductPayload({ name_en: "P" }, "t1", [], images, []);
    expect(result.images).toHaveLength(1);
  });

  it("maps color_set_id via colorSetIdxToId", () => {
    const variants: ProductVariantInput[] = [
      {
        sku: "V1",
        price: 10,
        is_active: true,
        color_set_id: "idx0",
      } as unknown as ProductVariantInput,
    ];
    const result = buildProductPayload({ name_en: "P" }, "t1", variants, [], [], false, [], [], {
      idx0: "real-uuid-1",
    });
    expect(result.variants).toEqual([
      { sku: "V1", price: 10, is_active: true, color_set_id: "real-uuid-1" },
    ]);
  });

  it("handles multi-piece payload", () => {
    const pieces = [{ name_en: "Top", name_ar: "قمة" }];
    const colorSets = [{ values: [{ color_option_id: "c1", piece_id: "p1" }] }];
    const result = buildProductPayload({ name_en: "P" }, "t1", [], [], [], true, pieces, colorSets);
    expect(result.is_multi_piece).toBe(true);
    expect(result.pieces).toEqual([{ name_en: "Top", name_ar: "قمة", sort_order: 0 }]);
    expect(result.color_sets).toEqual([
      { sort_order: 0, values: [{ piece_id: "p1", color_option_id: "c1" }] },
    ]);
  });

  it("skips pieces with empty name_en", () => {
    const pieces = [{ name_en: "", name_ar: "" }];
    const result = buildProductPayload({ name_en: "P" }, "t1", [], [], [], true, pieces);
    expect(result.pieces).toBeUndefined();
  });
});
