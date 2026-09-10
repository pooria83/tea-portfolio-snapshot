import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/components/chat/ProductGrid", () => ({
  ProductGrid: () => null,
}));

vi.mock("@/components/chat/CopyButton", () => ({
  CopyButton: () => null,
}));

vi.mock("@/components/chat/DebugButton", () => ({
  DebugButton: () => null,
}));

vi.mock("@/hooks/useChatScroll", () => ({
  useChatScroll: () => ({
    containerRef: { current: null },
    nearBottom: true,
    jumpToBottom: vi.fn(),
  }),
}));

import { ChatMessageList } from "../ChatMessageList";
import type { ChatViewMessage } from "@/lib/chatTypes";

const noop = () => {};

function userMessage(overrides: Partial<ChatViewMessage> = {}): ChatViewMessage {
  return {
    id: "u1",
    pairId: "p1",
    createdAt: 1,
    role: "user",
    kind: "message",
    content: "مرحبا",
    products: [],
    searchContext: null,
    debug: null,
    status: "completed",
    error: null,
    ...overrides,
  };
}

function assistantMessage(overrides: Partial<ChatViewMessage> = {}): ChatViewMessage {
  return {
    id: "a1",
    pairId: "p1",
    createdAt: 2,
    role: "assistant",
    kind: "message",
    content: "تفضل هذه النتائج",
    products: [],
    searchContext: null,
    debug: null,
    status: "completed",
    error: null,
    ...overrides,
  };
}

describe("ChatMessageList", () => {
  it("sets dir=rtl on assistant content when the message locale is rtl", () => {
    const { container } = render(
      <ChatMessageList
        messages={[userMessage({ locale: "ar" }), assistantMessage({ locale: "ar" })]}
        namespace="website.chat"
        onSelectProduct={noop}
        onFindSimilar={noop}
        onRetry={noop}
        onDebugOpen={noop}
      />,
    );
    const rtl = container.querySelector('div[dir="rtl"]');
    expect(rtl).not.toBeNull();
  });

  it("does not set dir=rtl for ltr assistant content", () => {
    const { container } = render(
      <ChatMessageList
        messages={[userMessage(), assistantMessage({ locale: "en" })]}
        namespace="website.chat"
        onSelectProduct={noop}
        onFindSimilar={noop}
        onRetry={noop}
        onDebugOpen={noop}
      />,
    );
    expect(container.querySelector('div[dir="rtl"]')).toBeNull();
  });

  it("falls back to dir=auto on assistant content when the message has no locale", () => {
    const { container } = render(
      <ChatMessageList
        messages={[userMessage(), assistantMessage()]}
        namespace="website.chat"
        onSelectProduct={noop}
        onFindSimilar={noop}
        onRetry={noop}
        onDebugOpen={noop}
      />,
    );
    expect(container.querySelector('div[dir="auto"]')).not.toBeNull();
  });

  it("sets dir=auto on the user bubble", () => {
    const { container } = render(
      <ChatMessageList
        messages={[userMessage()]}
        namespace="website.chat"
        onSelectProduct={noop}
        onFindSimilar={noop}
        onRetry={noop}
        onDebugOpen={noop}
      />,
    );
    expect(container.querySelector('div[dir="auto"]')).not.toBeNull();
  });
});
