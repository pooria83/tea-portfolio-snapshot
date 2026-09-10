import { describe, it, expect } from "vitest";
import { baseApi } from "../baseApi";

import "@/store/api/fileApi";

const api = baseApi as unknown as {
  endpoints: Record<string, { initiate: (...args: unknown[]) => unknown } | undefined>;
};

describe("fileApi endpoints", () => {
  it("should have uploadFile endpoint", () => {
    expect(api.endpoints.uploadFile).toBeDefined();
  });

  it("should build upload query with FormData and maxSize", () => {
    const builder = api.endpoints.uploadFile!;
    const file = new File(["test"], "test.csv", { type: "text/csv" });
    const query = builder.initiate({ file, maxSize: 500 });
    expect(query).toBeDefined();
  });

  it("should build upload query without maxSize", () => {
    const builder = api.endpoints.uploadFile!;
    const file = new File(["test"], "test.csv", { type: "text/csv" });
    const query = builder.initiate({ file });
    expect(query).toBeDefined();
  });
});
