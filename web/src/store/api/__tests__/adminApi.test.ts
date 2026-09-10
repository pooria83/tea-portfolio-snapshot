import { describe, it, expect } from "vitest";
import { baseApi } from "../baseApi";

import "../adminApi";

const api = baseApi as unknown as {
  endpoints: Record<string, { initiate: (...args: unknown[]) => unknown } | undefined>;
};

describe("adminApi endpoints", () => {
  it("should have getLLMModels query", () => {
    expect(api.endpoints.getLLMModels).toBeDefined();
  });

  it("should have addLLMApiKey mutation", () => {
    expect(api.endpoints.addLLMApiKey).toBeDefined();
  });

  it("should have toggleLLMApiKey mutation", () => {
    expect(api.endpoints.toggleLLMApiKey).toBeDefined();
  });

  it("should have deleteLLMApiKey mutation", () => {
    expect(api.endpoints.deleteLLMApiKey).toBeDefined();
  });

  it("should have getLLMSettings query", () => {
    expect(api.endpoints.getLLMSettings).toBeDefined();
  });

  it("should have updateLLMSettings mutation", () => {
    expect(api.endpoints.updateLLMSettings).toBeDefined();
  });

  it("should have getPromptTemplates query", () => {
    expect(api.endpoints.getPromptTemplates).toBeDefined();
  });

  it("should have updatePromptTemplates mutation", () => {
    expect(api.endpoints.updatePromptTemplates).toBeDefined();
  });

  it("should have getSystemSettings query", () => {
    expect(api.endpoints.getSystemSettings).toBeDefined();
  });

  it("should have updateSystemSetting mutation", () => {
    expect(api.endpoints.updateSystemSetting).toBeDefined();
  });

  it("should have getCronProducts query", () => {
    expect(api.endpoints.getCronProducts).toBeDefined();
  });

  it("should have getCronProductDetail query", () => {
    expect(api.endpoints.getCronProductDetail).toBeDefined();
  });

  it("should have getCronSummary query", () => {
    expect(api.endpoints.getCronSummary).toBeDefined();
  });

  it("should have getEmbeddingCronProducts query", () => {
    expect(api.endpoints.getEmbeddingCronProducts).toBeDefined();
  });

  it("should have getEmbeddingCronProductDetail query", () => {
    expect(api.endpoints.getEmbeddingCronProductDetail).toBeDefined();
  });

  it("should initiate getLLMModels", () => {
    const result = api.endpoints.getLLMModels!.initiate();
    expect(result).toBeDefined();
  });

  it("should initiate getCronProducts with params", () => {
    const result = api.endpoints.getCronProducts!.initiate({
      status: "pending",
      skip: 0,
      limit: 10,
    });
    expect(result).toBeDefined();
  });

  it("should initiate getCronProductDetail with productId", () => {
    const result = api.endpoints.getCronProductDetail!.initiate("cp-1");
    expect(result).toBeDefined();
  });
});
