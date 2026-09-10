import { describe, it, expect } from "vitest";
import { baseApi } from "../baseApi";

import "../productApi";

const api = baseApi as unknown as {
  endpoints: Record<string, { initiate: (...args: unknown[]) => unknown } | undefined>;
};

describe("productApi endpoints", () => {
  it("should have getProductTypes query", () => {
    expect(api.endpoints.getProductTypes).toBeDefined();
  });

  it("should have getAttributeGroups query", () => {
    expect(api.endpoints.getAttributeGroups).toBeDefined();
  });

  it("should have getCategoryTree query", () => {
    expect(api.endpoints.getCategoryTree).toBeDefined();
  });

  it("should have getProductTypeAttributes query", () => {
    expect(api.endpoints.getProductTypeAttributes).toBeDefined();
  });

  it("should have getImageViewTypes query", () => {
    expect(api.endpoints.getImageViewTypes).toBeDefined();
  });

  it("should have getBrands query", () => {
    expect(api.endpoints.getBrands).toBeDefined();
  });

  it("should have getMyProductsStats query", () => {
    expect(api.endpoints.getMyProductsStats).toBeDefined();
  });

  it("should have getMyProductsPage query", () => {
    expect(api.endpoints.getMyProductsPage).toBeDefined();
  });

  it("should have getStoreProduct query", () => {
    expect(api.endpoints.getStoreProduct).toBeDefined();
  });

  it("should have createStoreProduct mutation", () => {
    expect(api.endpoints.createStoreProduct).toBeDefined();
  });

  it("should have updateStoreProduct mutation", () => {
    expect(api.endpoints.updateStoreProduct).toBeDefined();
  });

  it("should have generateProductDescription mutation", () => {
    expect(api.endpoints.generateProductDescription).toBeDefined();
  });

  it("should initiate getMyProductsStats", () => {
    const result = api.endpoints.getMyProductsStats!.initiate();
    expect(result).toBeDefined();
  });

  it("should initiate getMyProductsPage with skip and limit", () => {
    const result = api.endpoints.getMyProductsPage!.initiate({
      skip: 0,
      limit: 10,
    });
    expect(result).toBeDefined();
  });

  it("should initiate getStoreProduct with store_id and product_id", () => {
    const result = api.endpoints.getStoreProduct!.initiate({ store_id: "s-1", product_id: "p-1" });
    expect(result).toBeDefined();
  });

  it("should initiate getCategoryTree with product_type_id filter", () => {
    const result = api.endpoints.getCategoryTree!.initiate({ product_type_id: "pt-1" });
    expect(result).toBeDefined();
  });
});
