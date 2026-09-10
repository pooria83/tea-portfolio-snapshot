import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useIsMobile } from "../use-mobile";

function createMockMatchMedia(matches: boolean) {
  return vi.fn((_query: string) => ({
    matches,
    media: "",
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_event: string, handler: () => void) => {
      handler();
    }),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as (query: string) => MediaQueryList;
}

describe("useIsMobile", () => {
  beforeEach(() => {
    globalThis.matchMedia = createMockMatchMedia(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should return false on desktop-sized viewport", () => {
    globalThis.matchMedia = createMockMatchMedia(false);

    Object.defineProperty(globalThis, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1024,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  it("should return true on mobile-sized viewport", () => {
    globalThis.matchMedia = createMockMatchMedia(true);

    Object.defineProperty(globalThis, "innerWidth", {
      writable: true,
      configurable: true,
      value: 767,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it("should return false exactly at breakpoint boundary (768)", () => {
    globalThis.matchMedia = createMockMatchMedia(false);

    Object.defineProperty(globalThis, "innerWidth", {
      writable: true,
      configurable: true,
      value: 768,
    });

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  it("should update when media query changes", () => {
    const listeners: Array<() => void> = [];
    globalThis.matchMedia = vi.fn((_query: string) => ({
      matches: false,
      media: "",
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_event: string, handler: () => void) => {
        listeners.push(handler);
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as (query: string) => MediaQueryList;

    Object.defineProperty(globalThis, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1024,
    });

    const { result, rerender } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    Object.defineProperty(globalThis, "innerWidth", {
      writable: true,
      configurable: true,
      value: 767,
    });

    act(() => {
      for (const l of listeners) l();
    });

    rerender();
    expect(result.current).toBe(true);
  });
});
