import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useChatSocket } from "../useChatSocket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  protocols: string | string[] | undefined;
  readyState: number = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  private listeners: Record<string, Array<(event: Event) => void>> = {};

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: (event: Event) => void) {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener];
  }

  removeEventListener(type: string, listener: (event: Event) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((entry) => entry !== listener);
  }

  private emit(type: string, event: Event = new Event(type)) {
    for (const listener of this.listeners[type] ?? []) {
      listener(event);
    }
  }

  send(data: string) {
    this.sent.push(data);
  }

  close(code = 1000) {
    if (this.readyState !== FakeWebSocket.CLOSED) {
      this.readyState = FakeWebSocket.CLOSED;
      this.emit("close", { code } as unknown as Event);
    }
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.emit("open");
  }

  receive(frame: Record<string, unknown>) {
    this.emit("message", { data: JSON.stringify(frame) } as MessageEvent<string>);
  }

  receiveRaw(data: string) {
    this.emit("message", { data } as MessageEvent<string>);
  }
}

describe("useChatSocket", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    FakeWebSocket.instances = [];
    vi.restoreAllMocks();
  });

  it("should not connect without conversationId", () => {
    const { result } = renderHook(() => useChatSocket({ conversationId: null, onFrame: () => {} }));
    expect(result.current.status).toBe("idle");
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("should connect and report open", () => {
    const { result } = renderHook(() =>
      useChatSocket({ conversationId: "conv-1", onFrame: () => {} }),
    );
    expect(result.current.status).toBe("connecting");
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0]?.url).toBe("ws://localhost:8000/api/v1/ws/chat/conv-1");
    expect(FakeWebSocket.instances[0]?.url).not.toContain("token");
    expect(FakeWebSocket.instances[0]?.protocols).toBeUndefined();

    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    expect(result.current.status).toBe("open");
  });

  it("should pass tokenOverride as the WebSocket subprotocol", () => {
    const { result } = renderHook(() =>
      useChatSocket({
        conversationId: "conv-1",
        tokenOverride: "anonymous-token",
        onFrame: () => {},
      }),
    );
    expect(result.current.status).toBe("connecting");
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0]?.url).toBe("ws://localhost:8000/api/v1/ws/chat/conv-1");
    expect(FakeWebSocket.instances[0]?.url).not.toContain("token");
    expect(FakeWebSocket.instances[0]?.protocols).toEqual(["anonymous-token"]);
  });

  it("should deliver parsed frames to the onFrame listener", () => {
    const onFrame = vi.fn();
    const { result } = renderHook(() => useChatSocket({ conversationId: "conv-1", onFrame }));
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      FakeWebSocket.instances[0]?.receive({ type: "text_chunk", delta: "hello" });
    });
    expect(onFrame).toHaveBeenCalledWith({ type: "text_chunk", delta: "hello" });
    expect(result.current.status).toBe("open");
  });

  it("should ignore invalid frames without calling onFrame", () => {
    const onFrame = vi.fn();
    renderHook(() => useChatSocket({ conversationId: "conv-1", onFrame }));
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      FakeWebSocket.instances[0]?.receiveRaw("not-json");
    });
    expect(onFrame).not.toHaveBeenCalled();
  });

  it("should send a raw frame immediately when open", () => {
    const { result } = renderHook(() =>
      useChatSocket({ conversationId: "conv-1", onFrame: () => {} }),
    );
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      result.current.sendFrame('{"type":"send_message","content":"hi"}');
    });
    expect(FakeWebSocket.instances[0]?.sent).toEqual(['{"type":"send_message","content":"hi"}']);
  });

  it("should queue a frame while closed and flush it after reconnect", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() =>
      useChatSocket({ conversationId: "conv-1", onFrame: () => {} }),
    );
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      FakeWebSocket.instances[0]?.close();
    });
    expect(result.current.status).toBe("reconnecting");

    act(() => {
      result.current.sendFrame('{"type":"ping"}');
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(FakeWebSocket.instances).toHaveLength(2);

    act(() => {
      FakeWebSocket.instances[1]?.open();
    });
    expect(result.current.status).toBe("open");
    expect(FakeWebSocket.instances[1]?.sent).toEqual(['{"type":"ping"}']);
    vi.useRealTimers();
  });

  it("should send keepalive ping frames while open", () => {
    vi.useFakeTimers();
    renderHook(() => useChatSocket({ conversationId: "conv-1", onFrame: () => {} }));
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    const socket = FakeWebSocket.instances[0]!;
    expect(JSON.parse(socket.sent[0] ?? "{}")).toEqual({ type: "ping" });
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    expect(JSON.parse(socket.sent[1] ?? "{}")).toEqual({ type: "ping" });
    vi.useRealTimers();
  });

  it("should force-close after MAX_MISSED_PINGS unanswered pings", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() =>
      useChatSocket({ conversationId: "conv-1", onFrame: () => {} }),
    );
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(FakeWebSocket.instances[0]?.readyState).toBe(FakeWebSocket.CLOSED);
    expect(result.current.status).toBe("reconnecting");
    vi.useRealTimers();
  });

  it("should reset missed pings on any received frame", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() =>
      useChatSocket({ conversationId: "conv-1", onFrame: () => {} }),
    );
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    act(() => {
      FakeWebSocket.instances[0]?.receive({ type: "ping" });
    });
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    expect(FakeWebSocket.instances[0]?.readyState).toBe(FakeWebSocket.OPEN);
    expect(result.current.status).toBe("open");
    vi.useRealTimers();
  });

  it("should not reconnect after auth-close (4001)", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() =>
      useChatSocket({ conversationId: "conv-1", onFrame: () => {} }),
    );
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      FakeWebSocket.instances[0]?.close(4001);
    });
    expect(result.current.status).toBe("closed");
    act(() => {
      vi.advanceTimersByTime(120_000);
    });
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.useRealTimers();
  });
});
