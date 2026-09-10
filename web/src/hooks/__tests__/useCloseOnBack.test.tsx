import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCloseOnBack } from "../useCloseOnBack";

describe("useCloseOnBack", () => {
  const originalPushState = window.history.pushState;
  const originalReplaceState = window.history.replaceState;

  beforeEach(() => {
    vi.clearAllMocks();
    window.history.pushState = originalPushState;
    window.history.replaceState = originalReplaceState;
  });

  it("does not push history or listen when closed", () => {
    const pushSpy = vi.spyOn(window.history, "pushState");
    const onClose = vi.fn();
    renderHook(() => useCloseOnBack(false, onClose, "test-1"));

    expect(pushSpy).not.toHaveBeenCalled();
  });

  it("closes the overlay on popstate when it is the topmost", () => {
    const onClose = vi.fn();
    const { unmount } = renderHook(() => useCloseOnBack(true, onClose, "test-2"));

    act(() => {
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    expect(onClose).toHaveBeenCalledTimes(1);

    unmount();
    act(() => {
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close the overlay on popstate when it is not the topmost", () => {
    const onCloseBottom = vi.fn();
    const onCloseTop = vi.fn();
    const bottom = renderHook(() => useCloseOnBack(true, onCloseBottom, "bottom"));
    const top = renderHook(() => useCloseOnBack(true, onCloseTop, "top"));

    act(() => {
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    expect(onCloseTop).toHaveBeenCalledTimes(1);
    expect(onCloseBottom).not.toHaveBeenCalled();

    bottom.unmount();
    top.unmount();
  });

  it("restores the previous URL when closed via UI (replaceState)", () => {
    const replaceSpy = vi.spyOn(window.history, "replaceState");
    const onClose = vi.fn();
    const { unmount } = renderHook(() => useCloseOnBack(true, onClose, "test-3"));

    unmount();

    expect(replaceSpy).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
