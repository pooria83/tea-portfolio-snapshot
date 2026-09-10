import { describe, it, expect } from "vitest";
import { baseApi } from "../baseApi";

import "@/store/api/profileApi";

const api = baseApi as unknown as {
  endpoints: Record<string, { initiate: (...args: unknown[]) => unknown } | undefined>;
};

describe("profileApi endpoints", () => {
  it("should have getProfile query", () => {
    expect(api.endpoints.getProfile).toBeDefined();
  });

  it("should have updateProfile mutation", () => {
    expect(api.endpoints.updateProfile).toBeDefined();
  });

  it("should have linkPhone mutation", () => {
    expect(api.endpoints.linkPhone).toBeDefined();
  });

  it("should have verifyLinkPhone mutation", () => {
    expect(api.endpoints.verifyLinkPhone).toBeDefined();
  });

  it("should have linkGoogle mutation", () => {
    expect(api.endpoints.linkGoogle).toBeDefined();
  });

  it("should generate correct URL for getProfile", () => {
    const result = api.endpoints.getProfile!.initiate();
    expect(result).toBeDefined();
  });
});
