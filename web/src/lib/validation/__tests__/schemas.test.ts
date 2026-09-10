import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  withValidation,
  CategoryOptionSchema,
  StoreListItemSchema,
  AuthResponseSchema,
  PaginatedItemsSchema,
} from "../index";

describe("withValidation", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("returns data when validation passes", () => {
    const validate = withValidation(CategoryOptionSchema);
    const input = { data: { id: "cat1", name: "Clothing" } };
    expect(validate(input)).toEqual({ id: "cat1", name: "Clothing" });
  });

  it("logs error and still returns data when validation fails", () => {
    const validate = withValidation(CategoryOptionSchema);
    const input = { data: { id: "cat1" } };
    expect(validate(input)).toEqual({ id: "cat1" });
    expect(console.error).toHaveBeenCalled();
  });
});

describe("CategoryOptionSchema", () => {
  it("accepts valid category", () => {
    const result = CategoryOptionSchema.safeParse({ id: "c1", name: "Shoes" });
    expect(result.success).toBe(true);
  });

  it("rejects missing id", () => {
    const result = CategoryOptionSchema.safeParse({ name: "Shoes" });
    expect(result.success).toBe(false);
  });

  it("rejects missing name", () => {
    const result = CategoryOptionSchema.safeParse({ id: "c1" });
    expect(result.success).toBe(false);
  });
});

describe("StoreListItemSchema", () => {
  const validItem = {
    id: "s1",
    name: "My Store",
    category_name_ar: "ملابس",
    category_name_en: "Clothing",
    category_name_fa: "لباس",
    store_type_name_ar: "متجر",
    store_type_name_en: "Store",
    store_type_name_fa: "فروشگاه",
    logo_url: "https://example.com/logo.png",
    is_active: true,
    created_at: "2025-01-01T00:00:00Z",
  };

  it("accepts valid store list item", () => {
    const result = StoreListItemSchema.safeParse(validItem);
    expect(result.success).toBe(true);
  });

  it("accepts nullable logo_url", () => {
    const result = StoreListItemSchema.safeParse({ ...validItem, logo_url: null });
    expect(result.success).toBe(true);
  });

  it("rejects missing is_active", () => {
    const { is_active: _unused, ...rest } = validItem;
    void _unused;
    const result = StoreListItemSchema.safeParse(rest);
    expect(result.success).toBe(false);
  });
});

describe("AuthResponseSchema", () => {
  it("accepts valid auth response", () => {
    const result = AuthResponseSchema.safeParse({
      success: true,
      data: {
        access_token: "abc",
        refresh_token: "def",
        token_type: "bearer",
      },
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing access_token", () => {
    const result = AuthResponseSchema.safeParse({
      success: true,
      data: { refresh_token: "def", token_type: "bearer" },
    });
    expect(result.success).toBe(false);
  });
});

describe("PaginatedItemsSchema", () => {
  it("accepts valid paginated response", () => {
    const schema = PaginatedItemsSchema(StoreListItemSchema);
    const result = schema.safeParse({
      items: [
        {
          id: "s1",
          name: "Store",
          category_name_ar: "أ",
          category_name_en: "A",
          category_name_fa: "ب",
          store_type_name_ar: "ت",
          store_type_name_en: "T",
          store_type_name_fa: "ث",
          logo_url: null,
          is_active: true,
          created_at: "2025-01-01T00:00:00Z",
        },
      ],
      meta: { skip: 0, limit: 20, total: 1, has_next: false, has_previous: false },
    });
    expect(result.success).toBe(true);
    expect(result.data?.items).toHaveLength(1);
  });
});
