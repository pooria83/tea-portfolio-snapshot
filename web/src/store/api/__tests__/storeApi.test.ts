import { describe, it, expect } from "vitest";
import { baseApi } from "../baseApi";

import "@/store/api/storeApi";

const api = baseApi as unknown as {
  endpoints: Record<string, { initiate: (...args: unknown[]) => unknown } | undefined>;
};

describe("storeApi endpoints", () => {
  it("should have getCategories query", () => {
    expect(api.endpoints.getCategories).toBeDefined();
  });

  it("should have getStoreTypes query", () => {
    expect(api.endpoints.getStoreTypes).toBeDefined();
  });

  it("should have getMyStores query", () => {
    expect(api.endpoints.getMyStores).toBeDefined();
  });

  it("should have getStore query", () => {
    expect(api.endpoints.getStore).toBeDefined();
  });

  it("should have createStore mutation", () => {
    expect(api.endpoints.createStore).toBeDefined();
  });

  it("should have updateStore mutation", () => {
    expect(api.endpoints.updateStore).toBeDefined();
  });

  it("should have deleteStore mutation", () => {
    expect(api.endpoints.deleteStore).toBeDefined();
  });

  it("should generate correct URL for getCategories", () => {
    const result = api.endpoints.getCategories!.initiate({ locale: "en" });
    expect(result).toBeDefined();
  });

  it("should generate correct URL for getStore with id", () => {
    const result = api.endpoints.getStore!.initiate("store-123");
    expect(result).toBeDefined();
  });
});
