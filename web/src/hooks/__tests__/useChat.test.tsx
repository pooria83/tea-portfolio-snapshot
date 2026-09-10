import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { Provider } from "react-redux";

import { useChat } from "../useChat";
import { makeStore } from "@/store/store";
import type { ChatMessage } from "@/types/api";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState: number = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  private listeners: Record<string, Array<(event: Event) => void>> = {};

  constructor(_url: string, _protocols?: string | string[]) {
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
}

const savedMessage: ChatMessage = {
  id: "m1",
  conversation_id: "conv-1",
  role: "assistant",
  content: "Here you go",
  status: "completed",
  token_count: 10,
  product_snapshots: [],
  search_context: null,
  debug: null,
  feedback: null,
  created_at: "2026-01-01T00:00:00Z",
  error: null,
};

function wrapper({ children }: { children: ReactNode }) {
  const store = makeStore();
  return <Provider store={store}>{children}</Provider>;
}

describe("useChat", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubGlobal("crypto", { randomUUID: () => "uuid-1" });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    FakeWebSocket.instances = [];
    vi.restoreAllMocks();
  });

  function openConversation() {
    const result = renderHook(() => useChat({ conversationId: "conv-1" }), { wrapper });
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    return result;
  }

  it("should not send while idle (no conversation)", () => {
    const { result } = renderHook(() => useChat({ conversationId: null }), { wrapper });
    expect(result.current.status).toBe("idle");
    expect(result.current.canSend).toBe(false);
    expect(result.current.sendMessage("hello")).toBe(false);
    expect(result.current.messages).toHaveLength(0);
  });

  it("should append an optimistic turn and send the frame", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("red ones");
    });
    const socket = FakeWebSocket.instances[0]!;
    expect(socket.sent).toHaveLength(1);
    expect(JSON.parse(socket.sent[0]!)).toMatchObject({
      type: "send_message",
      content: "red ones",
      idempotency_key: "uuid-1",
      include_saved_message: true,
    });
    expect(result.current.messages).toHaveLength(2);
    const [user, assistant] = result.current.messages;
    expect(user).toMatchObject({ role: "user", content: "red ones", status: "pending" });
    expect(assistant).toMatchObject({ role: "assistant", content: "", status: "streaming" });
    expect(user?.pairId).toBe(assistant?.pairId);
    expect(result.current.streaming).toBe(true);
    expect(result.current.canSend).toBe(false);
  });

  it("should block a second send while a turn is active", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("first");
      result.current.sendMessage("second");
    });
    expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1);
    expect(result.current.messages).toHaveLength(2);
  });

  it("should accumulate stream frames into the active assistant message", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("red ones");
    });
    const socket = FakeWebSocket.instances[0]!;
    act(() => {
      socket.receive({
        type: "debug",
        debug: { prompt: { model: "m" }, response: { choices: [] } },
      });
      socket.receive({
        type: "assistant_start",
        search_context: { rewritten_query: "red", filters: null },
      });
      socket.receive({ type: "text_chunk", delta: "Here are " });
      socket.receive({ type: "text_chunk", delta: "some dresses" });
      socket.receive({
        type: "product_cards",
        products: [
          {
            id: "p1",
            name: "Red Dress",
            price: 10,
            currency: "USD",
            brand: null,
            image_url: null,
            buy_url: null,
            store_id: null,
          },
        ],
        locale: "en",
      });
    });
    const assistant = result.current.messages[1]!;
    expect(assistant.content).toBe("Here are some dresses");
    expect(assistant.products).toHaveLength(1);
    expect(assistant.searchContext).toEqual({ rewritten_query: "red", filters: null });
    expect(assistant.debug).toEqual({ prompt: { model: "m" }, response: { choices: [] } });
    expect(assistant.locale).toBe("en");
  });

  it("should complete the turn on assistant_end and unlock after message_saved", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("q");
    });
    act(() => {
      FakeWebSocket.instances[0]?.receive({ type: "assistant_end" });
    });
    expect(result.current.messages[1]?.status).toBe("completed");
    expect(result.current.streaming).toBe(false);
    expect(result.current.canSend).toBe(false);
    act(() => {
      FakeWebSocket.instances[0]?.receive({
        type: "message_saved",
        conversation_id: "conv-1",
        message: savedMessage,
        user_message: { ...savedMessage, id: "u1", role: "user", content: "q" },
      });
    });
    expect(result.current.canSend).toBe(true);
  });

  it("should reconcile the saved messages on message_saved", () => {
    const onTurnSaved = vi.fn();
    const { result } = renderHook(() => useChat({ conversationId: "conv-1", onTurnSaved }), {
      wrapper,
    });
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    act(() => {
      result.current.sendMessage("q");
    });
    const pairId = result.current.messages[0]?.pairId;
    act(() => {
      FakeWebSocket.instances[0]?.receive({
        type: "message_saved",
        conversation_id: "conv-1",
        message: savedMessage,
        user_message: { ...savedMessage, id: "u1", role: "user", content: "q" },
      });
    });
    const [user, assistant] = result.current.messages;
    expect(user).toMatchObject({ id: "u1", status: "saved" });
    expect(assistant).toMatchObject({ id: "m1", status: "saved", content: "Here you go" });
    expect(user?.pairId).toBe(pairId);
    expect(onTurnSaved).toHaveBeenCalledTimes(1);
    expect(result.current.canSend).toBe(true);
  });

  it("should mark the turn failed on error frame and unlock", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("q");
    });
    act(() => {
      FakeWebSocket.instances[0]?.receive({ type: "error", code: "chat_failed" });
    });
    expect(result.current.messages[0]?.status).toBe("failed");
    expect(result.current.messages[1]?.status).toBe("failed");
    expect(result.current.messages[1]?.error).toBe("chat_failed");
    expect(result.current.canSend).toBe(true);
  });

  it("should retry with the SAME idempotency key", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("q");
    });
    const firstKey = (
      JSON.parse(FakeWebSocket.instances[0]!.sent[0]!) as { idempotency_key: string }
    ).idempotency_key;
    act(() => {
      FakeWebSocket.instances[0]?.receive({ type: "error", code: "chat_failed" });
    });
    const failedUser = result.current.messages[0]!;
    act(() => {
      result.current.retry(failedUser);
    });
    const secondFrame = JSON.parse(FakeWebSocket.instances[0]!.sent[1]!) as {
      idempotency_key: string;
      content: string;
    };
    expect(secondFrame.idempotency_key).toBe(firstKey);
    expect(secondFrame.content).toBe("q");
    expect(result.current.messages[0]?.status).toBe("pending");
    expect(result.current.messages[1]?.status).toBe("streaming");
    expect(result.current.messages[1]?.content).toBe("");
  });

  it("should retry a saved error-intent turn with the SAME idempotency key", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("q");
    });
    const firstKey = (
      JSON.parse(FakeWebSocket.instances[0]!.sent[0]!) as { idempotency_key: string }
    ).idempotency_key;
    act(() => {
      FakeWebSocket.instances[0]?.receive({
        type: "message_saved",
        conversation_id: "conv-1",
        message: {
          ...savedMessage,
          search_context: { rewritten_query: null, filters: null, intent: "error" },
        },
        user_message: { ...savedMessage, id: "u1", role: "user", content: "q" },
      });
    });
    expect(result.current.messages[0]?.status).toBe("saved");
    expect(result.current.messages[1]?.status).toBe("saved");
    act(() => {
      result.current.retry(result.current.messages[0]!);
    });
    const secondFrame = JSON.parse(FakeWebSocket.instances[0]!.sent[1]!) as {
      idempotency_key: string;
      content: string;
    };
    expect(secondFrame.idempotency_key).toBe(firstKey);
    expect(secondFrame.content).toBe("q");
    expect(result.current.messages[0]?.status).toBe("pending");
    expect(result.current.messages[1]?.status).toBe("streaming");
  });

  it("should keep the error code when a failed turn is saved and retry with the SAME idempotency key", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("q");
    });
    const firstKey = (
      JSON.parse(FakeWebSocket.instances[0]!.sent[0]!) as { idempotency_key: string }
    ).idempotency_key;
    act(() => {
      FakeWebSocket.instances[0]?.receive({ type: "error", code: "embedding_failed" });
    });
    act(() => {
      FakeWebSocket.instances[0]?.receive({
        type: "message_saved",
        conversation_id: "conv-1",
        message: {
          ...savedMessage,
          content: "",
          status: "failed",
          error: "embedding_failed",
          search_context: { rewritten_query: null, filters: null, intent: "error" },
        },
        user_message: { ...savedMessage, id: "u1", role: "user", content: "q" },
      });
    });
    expect(result.current.messages[1]).toMatchObject({
      status: "saved",
      error: "embedding_failed",
    });
    expect(result.current.messages[1]?.searchContext).toMatchObject({ intent: "error" });
    act(() => {
      result.current.retry(result.current.messages[0]!);
    });
    const secondFrame = JSON.parse(FakeWebSocket.instances[0]!.sent[1]!) as {
      idempotency_key: string;
      content: string;
    };
    expect(secondFrame.idempotency_key).toBe(firstKey);
    expect(secondFrame.content).toBe("q");
    expect(result.current.messages[0]?.status).toBe("pending");
    expect(result.current.messages[1]?.status).toBe("streaming");
  });

  it("should append a similar chip turn on sendSimilar", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendSimilar(
        {
          id: "p-9",
          name: "Dress",
          brand: null,
          price: 10,
          currency: "USD",
          image_url: null,
          buy_url: null,
          store_id: null,
        },
        "Dress",
      );
    });
    const socket = FakeWebSocket.instances[0]!;
    expect(JSON.parse(socket.sent[0]!)).toMatchObject({
      type: "similar_request",
      product_id: "p-9",
      product_name: "Dress",
      include_saved_message: true,
    });
    expect(result.current.messages[0]?.kind).toBe("similar");
    expect(result.current.messages[0]?.status).toBe("pending");
    act(() => {
      socket.receive({ type: "assistant_end" });
      socket.receive({
        type: "message_saved",
        conversation_id: "conv-1",
        message: { ...savedMessage, id: "m-sim" },
      });
    });
    expect(result.current.messages[0]?.status).toBe("saved");
    expect(result.current.messages[1]?.status).toBe("saved");
  });

  it("should not send when blocked", () => {
    const { result } = renderHook(() => useChat({ conversationId: "conv-1", blocked: true }), {
      wrapper,
    });
    act(() => {
      FakeWebSocket.instances[0]?.open();
    });
    expect(result.current.canSend).toBe(false);
    expect(result.current.sendMessage("q")).toBe(false);
    expect(FakeWebSocket.instances[0]?.sent).toHaveLength(0);
  });

  it("should merge history deduped by server id", () => {
    const { result } = openConversation();
    const history: ChatMessage[] = [
      { ...savedMessage, id: "h1", role: "user" as const, content: "old q" },
      { ...savedMessage, id: "h2", role: "assistant" as const, content: "old a" },
    ];
    act(() => {
      result.current.mergeHistory(history);
      result.current.mergeHistory(history);
    });
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({ id: "h1", status: "saved" });
  });

  it("should reset the message list on demand", () => {
    const { result } = openConversation();
    act(() => {
      result.current.sendMessage("q");
    });
    expect(result.current.messages).toHaveLength(2);
    act(() => {
      result.current.reset();
    });
    expect(result.current.messages).toHaveLength(0);
  });
});
