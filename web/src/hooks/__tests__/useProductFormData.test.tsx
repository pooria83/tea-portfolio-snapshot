import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { Provider } from "react-redux";
import { makeStore } from "@/store/store";
import { useProductFormData } from "../useProductFormData";

const mockProductTypes = vi.hoisted(() => [{ id: "pt-1", name_en: "Clothing" }]);
const mockAttrGroups = vi.hoisted(() => [{ id: "g-1", code: "size", name_en: "Size" }]);
const mockCategoryTree = vi.hoisted(() => [
  {
    id: "cat-1",
    name_ar: "ملابس",
    name_en: "Clothing",
    name_fa: "لباس",
    parent_id: null,
    product_type_id: "pt-1",
    children: [
      {
        id: "cat-2",
        name_ar: "تيشرت",
        name_en: "T-Shirt",
        name_fa: "تیشرت",
        parent_id: "cat-1",
        product_type_id: "pt-1",
        children: [],
      },
    ],
  },
]);
const mockAttributes = vi.hoisted(() => [
  {
    id: "a-1",
    group_id: "g-1",
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
    is_visible_on_show: false,
    is_variant_defining: false,
    sort_order: 0,
    options: [{ id: "o-1", value_ar: "صغير", value_en: "S", value_fa: "کوچک" }],
    validation_rules: null,
  },
]);
const mockImageViewTypes = vi.hoisted(() => [{ id: "ivt-1", name: "default" }]);
const mockBrands = vi.hoisted(() => [
  { id: "b-1", name_ar: "نايك", name_en: "Nike", name_fa: "نایک" },
]);

vi.mock("next-intl", () => ({
  useLocale: () => "ar",
}));

vi.mock("@/store/api/productApi", () => ({
  useGetProductTypesQuery: () => ({ data: mockProductTypes }),
  useGetAttributeGroupsQuery: () => ({ data: mockAttrGroups }),
  useGetCategoryTreeQuery: () => ({ data: mockCategoryTree }),
  useGetProductTypeAttributesQuery: (_params: unknown, options?: { skip?: boolean }) =>
    options?.skip ? { data: [] } : { data: mockAttributes },
  useGetImageViewTypesQuery: () => ({ data: mockImageViewTypes }),
  useGetBrandsQuery: () => ({ data: mockBrands }),
  useCreateStoreProductMutation: () => [vi.fn(), { isLoading: false }],
  useUpdateStoreProductMutation: () => [vi.fn(), { isLoading: false }],
}));

function wrapper({ children }: { children: ReactNode }) {
  return <Provider store={makeStore()}>{children}</Provider>;
}

describe("useProductFormData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns data with product type id", () => {
    const { result } = renderHook(() => useProductFormData("pt-1"), { wrapper });
    expect(result.current.productTypes).toEqual(mockProductTypes);
    expect(result.current.attrGroups).toEqual(mockAttrGroups);
    expect(result.current.categoryTree).toEqual(mockCategoryTree);
    expect(result.current.allAttributes).toEqual(mockAttributes);
    expect(result.current.imageViewTypes).toEqual(mockImageViewTypes);
    expect(result.current.brands).toEqual(mockBrands);
    expect(result.current.creating).toBe(false);
    expect(result.current.updating).toBe(false);
  });

  it("computes groupCodeToId from attrGroups", () => {
    const { result } = renderHook(() => useProductFormData("pt-1"), { wrapper });
    expect(result.current.groupCodeToId).toEqual({ size: "g-1" });
  });

  it("groups attributes by group_id", () => {
    const { result } = renderHook(() => useProductFormData("pt-1"), { wrapper });
    expect(result.current.groupedAttributes["g-1"]).toHaveLength(1);
  });

  it("computes flatCategories with Arabic locale label", () => {
    const { result } = renderHook(() => useProductFormData("pt-1"), { wrapper });
    expect(result.current.flatCategories).toEqual([
      { id: "cat-1", label: "ملابس" },
      { id: "cat-2", label: "ملابس > تيشرت" },
    ]);
  });

  it("computes optionsMap from attributes", () => {
    const { result } = renderHook(() => useProductFormData("pt-1"), { wrapper });
    expect(result.current.optionsMap["a-1"]).toHaveLength(1);
    expect(result.current.optionsMap["a-1"]![0]!.value_en).toBe("S");
  });

  it("skips product type attributes when productTypeId is empty", () => {
    const { result } = renderHook(() => useProductFormData(""), { wrapper });
    expect(result.current.allAttributes).toEqual([]);
  });
});
