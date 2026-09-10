import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string) =>
    namespace === "common" && key === "scrollToTop" ? "Scroll to top" : key,
}));

import { ScrollToTop } from "@/components/shared/ScrollToTop";

function createMockMatchMedia(matches: boolean) {
  return vi.fn((_query: string) => ({
    matches,
    media: "",
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as (query: string) => MediaQueryList;
}

function setWindowScrollY(value: number) {
  Object.defineProperty(window, "scrollY", { value, configurable: true, writable: true });
}

describe("ScrollToTop", () => {
  beforeEach(() => {
    globalThis.matchMedia = createMockMatchMedia(false);
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
  });

  afterEach(() => {
    setWindowScrollY(0);
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("does not render when at the top of the page", () => {
    setWindowScrollY(0);
    render(<ScrollToTop />);
    expect(screen.queryByLabelText("Scroll to top")).not.toBeInTheDocument();
  });

  it("renders after the window is scrolled down", () => {
    setWindowScrollY(400);
    render(<ScrollToTop />);
    expect(screen.getByLabelText("Scroll to top")).toBeInTheDocument();
  });

  it("renders when an inner scroll container is scrolled", () => {
    render(<ScrollToTop />);
    const container = document.createElement("div");
    document.body.append(container);
    Object.defineProperty(container, "scrollTop", { value: 500, configurable: true });
    act(() => {
      container.dispatchEvent(new Event("scroll", { bubbles: true }));
    });
    expect(screen.getByLabelText("Scroll to top")).toBeInTheDocument();
    container.remove();
  });

  it("scrolls the window to top on click", () => {
    const scrollTo = vi.fn();
    window.scrollTo = scrollTo;
    setWindowScrollY(400);
    render(<ScrollToTop />);
    fireEvent.click(screen.getByLabelText("Scroll to top"));
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });

  it("hides again when scrolled back to the top", () => {
    setWindowScrollY(400);
    render(<ScrollToTop />);
    expect(screen.getByLabelText("Scroll to top")).toBeInTheDocument();
    setWindowScrollY(0);
    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });
    expect(screen.queryByLabelText("Scroll to top")).not.toBeInTheDocument();
  });

  it("does not render on mobile screens", () => {
    globalThis.matchMedia = createMockMatchMedia(true);
    Object.defineProperty(globalThis, "innerWidth", {
      writable: true,
      configurable: true,
      value: 390,
    });
    setWindowScrollY(400);
    render(<ScrollToTop />);
    expect(screen.queryByLabelText("Scroll to top")).not.toBeInTheDocument();
  });
});
