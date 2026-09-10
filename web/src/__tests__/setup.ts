import "@testing-library/jest-dom/vitest";

if (typeof ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

if (typeof IntersectionObserver === "undefined") {
  globalThis.IntersectionObserver = class IntersectionObserver {
    readonly root: Element | null = null;
    readonly rootMargin: string = "";
    readonly thresholds: readonly number[] = [];
    constructor(_callback: IntersectionObserverCallback, _options?: IntersectionObserverInit) {}
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  } as unknown as typeof IntersectionObserver;
}

if (typeof requestAnimationFrame === "undefined") {
  globalThis.requestAnimationFrame = () => 0;
}

// input-otp uses setTimeout that calls React's resolveUpdatePriority
// which accesses window in dev mode — jsdom teardown can delete it,
// leaving a ReferenceError from lingering timers.
// Use a getter/setter that captures jsdom's window when set,
// but returns globalThis as fallback when jsdom clears it.
{
  let _window: typeof globalThis | undefined =
    globalThis.window === undefined ? undefined : globalThis.window;
  Object.defineProperty(globalThis, "window", {
    get() {
      return _window ?? globalThis;
    },
    set(val) {
      _window = val;
    },
    configurable: true,
  });
}
