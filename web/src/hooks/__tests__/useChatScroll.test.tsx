import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useChatScroll } from "../useChatScroll";

function mockContainer() {
  const scrollTo = vi.fn();
  const container = {
    scrollTop: 0,
    scrollHeight: 1000,
    clientHeight: 500,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    scrollTo,
  } as unknown as HTMLDivElement;
  return { container, scrollTo };
}

function mountWithContainer(messages: unknown[]) {
  const { container, scrollTo } = mockContainer();
  const hook = renderHook((props: { messages: unknown[] }) => useChatScroll(props), {
    initialProps: { messages },
  });
  act(() => {
    hook.result.current.containerRef(container);
  });
  return { ...hook, container, scrollTo };
}

describe("useChatScroll", () => {
  it("should start near the bottom with no container", () => {
    const { result } = renderHook(() => useChatScroll({ messages: [] }));
    expect(result.current.nearBottom).toBe(true);
  });

  it("should update nearBottom on scroll events", () => {
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    try {
      const { container, result } = mountWithContainer([]);
      const scrollHandler = (container.addEventListener as ReturnType<typeof vi.fn>).mock
        .calls[0]?.[1] as () => void;

      act(() => {
        container.scrollTop = 400;
        scrollHandler();
      });
      expect(result.current.nearBottom).toBe(false);

      act(() => {
        container.scrollTop = 450;
        scrollHandler();
      });
      expect(result.current.nearBottom).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("should autoscroll when a new message arrives while near the bottom", () => {
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    const { scrollTo, rerender } = mountWithContainer([{ id: "1" }]);
    rerender({ messages: [{ id: "1" }, { id: "2" }] });
    expect(scrollTo).toHaveBeenCalledWith({ top: 1000 });
    vi.unstubAllGlobals();
  });

  it("should NOT autoscroll on content updates while far from the bottom", () => {
    const { container, scrollTo, rerender } = mountWithContainer([{ id: "1", content: "a" }]);
    const callsAfterMount = scrollTo.mock.calls.length;

    act(() => {
      container.scrollTop = 200;
    });
    rerender({ messages: [{ id: "1", content: "ab" }] });
    expect(scrollTo.mock.calls.length).toBe(callsAfterMount);
  });

  it("should smooth-scroll via jumpToBottom", () => {
    const { result, scrollTo } = mountWithContainer([{ id: "1" }]);
    act(() => {
      result.current.jumpToBottom();
    });
    expect(scrollTo).toHaveBeenCalledWith({ top: 1000, behavior: "smooth" });
  });
});
