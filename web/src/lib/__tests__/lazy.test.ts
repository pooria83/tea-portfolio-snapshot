import { describe, it, expect, vi, beforeEach } from "vitest";

const mockDynamic = vi.hoisted(() => vi.fn());

vi.mock("next/dynamic", () => ({
  default: mockDynamic,
}));

import { lazyImport } from "../lazy";

describe("lazyImport", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls next/dynamic with ssr: false by default", () => {
    const importFn = () => Promise.resolve({ default: (() => null) as never });
    lazyImport(importFn);
    expect(mockDynamic).toHaveBeenCalledWith(importFn, { ssr: false });
  });

  it("passes ssr: true when specified", () => {
    const importFn = () => Promise.resolve({ default: (() => null) as never });
    lazyImport(importFn, { ssr: true });
    expect(mockDynamic).toHaveBeenCalledWith(importFn, { ssr: true });
  });

  it("passes loading component when provided", () => {
    const importFn = () => Promise.resolve({ default: (() => null) as never });
    const Loading = () => null;
    lazyImport(importFn, { loading: Loading });
    expect(mockDynamic).toHaveBeenCalledWith(importFn, {
      ssr: false,
      loading: Loading,
    });
  });
});
