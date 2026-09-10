import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import type { ReactNode } from "react";

import { AnonymousChatBox } from "../AnonymousChatBox";
import { makeStore } from "@/store/store";
import type { ChatProduct } from "@/types/api";
import type { ChatViewMessage } from "@/lib/chatTypes";

const messages: Record<string, Record<string, string>> = {
  "website.chat": {
    title: "Ask Our AI Assistant",
    description: "Get product recommendations instantly.",
    placeholder: "Ask about products, styles, or outfits...",
    inputPlaceholder: "Search for products, styles, or outfits...",
    back: "Back",
    send: "Send",
    connecting: "Connecting...",
    reconnecting: "Reconnecting...",
    thinking: "Thinking...",
    error: "Something went wrong.",
    findingSimilar: "Finding similar to {name}…",
    retry: "Retry",
    jumpToBottom: "Jump to bottom",
    copyMessage: "Copy message",
    copied: "Copied",
    debug: "Debug",
  },
  "admin.productSearch": {
    findSimilar: "Find similar products",
  },
  errors: { product_not_found: "Product not found" },
};

const sessionResult = {
  token: "anon-token",
  conversation: {
    id: "anon-conv-1",
    title: null,
    status: "active",
    user_message_count: 0,
    last_activity_at: "2026-08-13T00:00:00Z",
    locale: "en",
    created_at: "2026-08-13T00:00:00Z",
    updated_at: "2026-08-13T00:00:00Z",
  },
};

const dress: ChatProduct = {
  id: "p1",
  name: "Red Dress",
  price: 10,
  currency: "USD",
  brand: "Brand A",
  image_url: null,
  buy_url: null,
  store_id: "s1",
};

function savedView(overrides: Partial<ChatViewMessage>): ChatViewMessage {
  return {
    id: "m1",
    pairId: "pair-1",
    createdAt: 1,
    role: "assistant",
    kind: "message",
    content: "Here are some dresses",
    products: [dress],
    searchContext: null,
    debug: null,
    status: "saved",
    error: null,
    ...overrides,
  };
}

const mockChat = {
  messages: [] as ChatViewMessage[],
  status: "open",
  canSend: true,
  streaming: false,
  sendMessage: vi.fn().mockReturnValue(true),
  sendSimilar: vi.fn().mockReturnValue(true),
  retry: vi.fn().mockReturnValue(true),
};

let chatOptions: {
  conversationId?: string | null;
  tokenOverride?: string | null;
} = {};

const getSession = vi.fn().mockReturnValue({ unwrap: () => Promise.resolve(sessionResult) });

vi.mock("@/store/api/anonymousApi", () => ({
  useGetAnonymousChatSessionMutation: () => [getSession, { isLoading: false }],
}));

vi.mock("@/hooks/useChat", () => ({
  useChat: (options: { conversationId?: string | null; tokenOverride?: string | null }) => {
    chatOptions = options;
    return mockChat;
  },
}));

vi.mock("next/image", () => ({
  __esModule: true,
  default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) => (
    <img alt={alt} {...props} />
  ),
}));

vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: (namespace: string) => {
    const table = messages[namespace as keyof typeof messages] ?? {};
    return (key: string) => (table as Record<string, string>)[key] ?? key;
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  return <Provider store={makeStore()}>{children}</Provider>;
}

describe("AnonymousChatBox", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockChat.messages = [];
    mockChat.status = "open";
    mockChat.canSend = true;
    mockChat.streaming = false;
    mockChat.sendMessage.mockReturnValue(true);
    mockChat.sendSimilar.mockReturnValue(true);
    getSession.mockReturnValue({ unwrap: () => Promise.resolve(sessionResult) });
    chatOptions = {};
  });

  it("creates an anonymous session and passes it to useChat", async () => {
    render(<AnonymousChatBox />, { wrapper });
    await waitFor(() => {
      expect(getSession).toHaveBeenCalledWith({ locale: "en" });
    });
    await waitFor(() => {
      expect(chatOptions.conversationId).toBe("anon-conv-1");
    });
    expect(chatOptions.tokenOverride).toBe("anon-token");
  });

  it("sends a message through useChat and renders optimistic + saved messages", async () => {
    const { rerender } = render(<AnonymousChatBox />, { wrapper });
    await waitFor(() => {
      expect(chatOptions.conversationId).toBe("anon-conv-1");
    });

    fireEvent.change(screen.getByLabelText("Search for products, styles, or outfits..."), {
      target: { value: "red dress" },
    });
    fireEvent.click(screen.getByLabelText("Send"));
    expect(mockChat.sendMessage).toHaveBeenCalledWith("red dress");

    mockChat.messages = [
      savedView({ id: "u1", role: "user", content: "red dress", pairId: "pair-1" }),
      savedView({ pairId: "pair-1" }),
    ];
    rerender(<AnonymousChatBox />);
    await waitFor(() => {
      expect(screen.getByText("Here are some dresses")).toBeInTheDocument();
    });
  });

  it("renders streamed product cards and sends a similar request", async () => {
    const { rerender } = render(<AnonymousChatBox />, { wrapper });
    await waitFor(() => {
      expect(chatOptions.conversationId).toBe("anon-conv-1");
    });

    fireEvent.change(screen.getByLabelText("Search for products, styles, or outfits..."), {
      target: { value: "red dress" },
    });
    fireEvent.click(screen.getByLabelText("Send"));

    mockChat.messages = [savedView({ pairId: "pair-1" })];
    rerender(<AnonymousChatBox />);

    expect(screen.getByText("Red Dress")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Find similar products"));
    expect(mockChat.sendSimilar).toHaveBeenCalledWith(dress, "Red Dress");
  });

  it("does not send while the assistant is streaming", async () => {
    mockChat.streaming = true;
    mockChat.canSend = false;
    render(<AnonymousChatBox />, { wrapper });
    await waitFor(() => {
      expect(chatOptions.conversationId).toBe("anon-conv-1");
    });

    fireEvent.change(screen.getByLabelText("Search for products, styles, or outfits..."), {
      target: { value: "second question" },
    });
    fireEvent.click(screen.getByLabelText("Send"));

    expect(mockChat.sendMessage).not.toHaveBeenCalled();
  });
});
