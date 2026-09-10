import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useInfiniteProducts } from "../useInfiniteProducts";
import type { PaginationMeta } from "@/types/api";

function makeMeta(overrides: Partial<PaginationMeta> = {}): PaginationMeta {
  return {
    skip: 0,
    limit: 20,
    total: 0,
    has_next: false,
    has_previous: false,
    ...overrides,
  };
}

function makeFetchPage(result: { items: { id: string }[]; meta: PaginationMeta }) {
  return vi.fn().mockResolvedValue({ data: result });
}

function stubIntersectionObserver() {
  const observe = vi.fn();
  const disconnect = vi.fn();
  const impl = vi.fn(function (_cb: IntersectionObserverCallback) {
    return { observe, disconnect, unobserve: vi.fn(), root: null, rootMargin: "", thresholds: [] };
  }) as unknown as typeof IntersectionObserver;
  vi.stubGlobal("IntersectionObserver", impl);
  return { observe, disconnect };
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useInfiniteProducts", () => {
  it("returns initial loading state", () => {
    const fetchPage = makeFetchPage({ items: [], meta: makeMeta() });
    const { result } = renderHook(() => useInfiniteProducts(fetchPage));
    expect(result.current.items).toEqual([]);
    expect(result.current.total).toBe(0);
    expect(result.current.hasMore).toBe(true);
    expect(result.current.isLoading).toBe(true);
  });

  it("loads items on mount", async () => {
    const fetchPage = makeFetchPage({ items: [{ id: "p-1" }], meta: makeMeta({ total: 1 }) });
    const { result } = renderHook(() => useInfiniteProducts(fetchPage));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.items).toHaveLength(1);
    expect(result.current.total).toBe(1);
    expect(result.current.hasMore).toBe(false);
  });

  it("deduplicates items with same id across pages", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({
        data: { items: [{ id: "p-1" }], meta: makeMeta({ total: 2, has_next: true }) },
      })
      .mockResolvedValueOnce({
        data: { items: [{ id: "p-1" }, { id: "p-2" }], meta: makeMeta({ total: 2 }) },
      });

    const { result } = renderHook(() => useInfiniteProducts(fetchPage));

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.refresh();
    });

    await waitFor(() => {
      expect(result.current.items).toHaveLength(2);
    });
  });

  it("handles fetchPage returning undefined data", async () => {
    const fetchPage = vi.fn().mockResolvedValue({ data: undefined });
    const { result } = renderHook(() => useInfiniteProducts(fetchPage));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.items).toEqual([]);
  });

  it("handles fetchPage throwing an error", async () => {
    const fetchPage = vi.fn().mockRejectedValue(new Error("Network error"));
    const { result } = renderHook(() => useInfiniteProducts(fetchPage));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(console.error).toHaveBeenCalled();
  });

  it("refresh resets and reloads", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ data: { items: [{ id: "p-1" }], meta: makeMeta({ total: 10 }) } })
      .mockResolvedValueOnce({ data: { items: [{ id: "p-2" }], meta: makeMeta({ total: 5 }) } });

    const { result } = renderHook(() => useInfiniteProducts(fetchPage));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toHaveLength(1);

    await act(async () => {
      await result.current.refresh();
    });

    await waitFor(() => {
      expect(result.current.items).toHaveLength(1);
    });
  });

  it("renders sentinel callback ref", () => {
    stubIntersectionObserver();
    const fetchPage = makeFetchPage({ items: [], meta: makeMeta({ has_next: true }) });

    const { result } = renderHook(() => useInfiniteProducts(fetchPage));

    const div = document.createElement("div");
    act(() => {
      result.current.sentinelRef(div);
    });
  });
});
