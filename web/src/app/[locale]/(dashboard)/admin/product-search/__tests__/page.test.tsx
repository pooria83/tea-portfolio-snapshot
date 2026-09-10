import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { Provider } from "react-redux";
import type { ReactNode } from "react";

import ProductSearchPage from "../page";
import { makeStore } from "@/store/store";
import type { ChatMessage, ConversationItem } from "@/types/api";
import type { ChatViewMessage } from "@/lib/chatTypes";

const messages: Record<string, Record<string, string>> = {
  "admin.productSearch": {
    title: "Product Search",
    description: "Search products",
    placeholder: "Ask about products",
    inputPlaceholder: "Type your product query...",
    send: "Search",
    connecting: "Connecting...",
    thinking: "Searching products...",
    error: "Search failed",
    retry: "Retry",
    newChat: "New Chat",
    openConversations: "Open conversations",
    loading: "Loading conversations...",
    noConversations: "No conversations yet",
    closedBadge: "Closed",
    closedNote: "This conversation is closed and read-only.",
    deleteChat: "Delete conversation",
    deleteConfirm: "Delete this conversation? This cannot be undone.",
    copyMessage: "Copy",
    copied: "Copied!",
    debug: "Debug",
    debugTitle: "LLM Debug Info",
    debugPrompt: "Prompt",
    debugResponse: "Response",
    findSimilar: "Find similar products",
    jumpToBottom: "Jump to bottom",
  },
  common: { cancel: "Cancel", delete: "Delete", close: "Close" },
  errors: { product_not_found: "Product not found", embedding_failed: "Search failed" },
};

const conversationA: ConversationItem = {
  id: "conv-a",
  title: "Short dress hunt",
  status: "active",
  user_message_count: 2,
  last_activity_at: "2026-08-05T10:00:00Z",
  locale: "en",
  created_at: "2026-08-05T09:00:00Z",
  updated_at: "2026-08-05T10:00:00Z",
};

const conversationB: ConversationItem = {
  id: "conv-b",
  title: "Summer collection",
  status: "closed",
  user_message_count: 1,
  last_activity_at: "2026-08-04T08:00:00Z",
  locale: "en",
  created_at: "2026-08-04T07:00:00Z",
  updated_at: "2026-08-04T08:00:00Z",
};

const historyMessages: ChatMessage[] = [
  {
    id: "m1",
    conversation_id: "conv-a",
    role: "user",
    content: "i want short dress",
    status: "completed",
    token_count: 3,
    product_snapshots: [],
    search_context: null,
    debug: null,
    feedback: null,
    created_at: "2026-08-05T09:01:00Z",
    error: null,
  },
  {
    id: "m2",
    conversation_id: "conv-a",
    role: "assistant",
    content: "Here are some dresses",
    status: "completed",
    token_count: 10,
    product_snapshots: [
      {
        id: "p1",
        name: "Red Dress",
        price: 10,
        currency: "USD",
        brand: "Brand A",
        image_url: null,
        buy_url: null,
        store_id: "s1",
      },
    ],
    search_context: { rewritten_query: "short dress", filters: null },
    debug: null,
    feedback: null,
    created_at: "2026-08-05T09:01:05Z",
    error: null,
  },
];

function viewFromChatMessage(message: ChatMessage, index: number): ChatViewMessage {
  return {
    id: message.id,
    pairId: `h-${message.id}`,
    createdAt: new Date(message.created_at).getTime() + index,
    role: message.role,
    kind: "message",
    content: message.content,
    products: message.product_snapshots,
    ...(message.locale ? { locale: message.locale } : {}),
    searchContext: message.search_context,
    debug: message.debug,
    status: "saved",
    error: message.error,
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
  mergeHistory: vi.fn(),
};

let chatOptions: {
  conversationId?: string | null;
  blocked?: boolean;
} = {};

let chatsResult: { data: ConversationItem[] | undefined; isLoading: boolean } = {
  data: [conversationA, conversationB],
  isLoading: false,
};

const createConversation = vi.fn();
const deleteConversation = vi.fn();

vi.mock("@/store/api/chatApi", () => ({
  useGetMyChatsQuery: () => chatsResult,
  useCreateConversationMutation: () => [createConversation, { isLoading: false }],
  useDeleteConversationMutation: () => [deleteConversation, { isLoading: false }],
  useGetChatMessagesQuery: (args: { conversationId: string }) => ({
    data: args.conversationId === "conv-a" ? historyMessages : [],
    isLoading: false,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/hooks/useChat", () => ({
  useChat: (options: { conversationId?: string | null; blocked?: boolean }) => {
    chatOptions = options;
    return { ...mockChat, canSend: !options.blocked && mockChat.canSend };
  },
}));

const uiLocale = vi.hoisted(() => ({ value: "en" }));

vi.mock("next/image", () => ({
  __esModule: true,
  default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) => (
    <img alt={alt} {...props} />
  ),
}));

vi.mock("next-intl", () => ({
  useLocale: () => uiLocale.value,
  useTranslations: (namespace: string) => {
    const table = messages[namespace as keyof typeof messages] ?? {};
    return (key: string) => (table as Record<string, string>)[key] ?? key;
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  return <Provider store={makeStore()}>{children}</Provider>;
}

describe("ProductSearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatsResult = { data: [conversationA, conversationB], isLoading: false };
    chatOptions = {};
    uiLocale.value = "en";
    mockChat.messages = [];
    mockChat.status = "open";
    mockChat.canSend = true;
    mockChat.streaming = false;
    mockChat.sendMessage.mockReturnValue(true);
    mockChat.sendSimilar.mockReturnValue(true);
    mockChat.retry.mockReturnValue(true);
    mockChat.mergeHistory.mockImplementation((history: ChatMessage[]) => {
      const existingIds = new Set(mockChat.messages.map((message) => message.id));
      const fresh = history
        .filter((message) => !existingIds.has(message.id))
        .map((message, index) => viewFromChatMessage(message, index + 1));
      mockChat.messages = [...mockChat.messages, ...fresh];
    });
    mockChat.messages = historyMessages.map((message, index) =>
      viewFromChatMessage(message, index + 1),
    );
  });

  it("should render sidebar with conversations and history", () => {
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("Short dress hunt")).toBeTruthy();
    expect(screen.getByText("Summer collection")).toBeTruthy();
    expect(screen.getByText("Closed")).toBeTruthy();
    expect(screen.getByText("i want short dress")).toBeTruthy();
    expect(screen.getByText("Here are some dresses")).toBeTruthy();
    expect(screen.getByText("Red Dress")).toBeTruthy();
  });

  it("should open product dialog when clicking a product card", () => {
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByText("Red Dress"));
    expect(screen.getByText("Red Dress")).toBeTruthy();
  });

  it("should send a similar request when the find-similar button is clicked", () => {
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByLabelText("Find similar products"));
    expect(mockChat.sendSimilar).toHaveBeenCalledWith(
      historyMessages[1]!.product_snapshots[0]!,
      "Red Dress",
    );
    fireEvent.click(screen.getByText("Red Dress"));
    expect(mockChat.sendSimilar).toHaveBeenCalledTimes(1);
  });

  it("should show product_not_found failure text for a similar request", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-fail",
        status: "failed",
        error: "product_not_found",
        products: [],
      },
    ];
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("Product not found")).toBeTruthy();
  });

  it("should send message through useChat and render the optimistic user message", () => {
    const { rerender } = render(<ProductSearchPage />, { wrapper });
    fireEvent.change(screen.getByPlaceholderText("Type your product query..."), {
      target: { value: "i want red ones" },
    });
    fireEvent.click(screen.getByText("Search"));
    expect(mockChat.sendMessage).toHaveBeenCalledWith("i want red ones");
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      viewFromChatMessage(historyMessages[1]!, 2),
      {
        ...viewFromChatMessage(historyMessages[0]!, 3),
        id: "u-new",
        content: "i want red ones",
        createdAt: 3,
      },
    ];
    rerender(<ProductSearchPage />);
    expect(screen.getByText("i want red ones")).toBeTruthy();
  });

  it("should show streaming assistant bubble while stream is active", () => {
    mockChat.streaming = true;
    mockChat.canSend = false;
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-stream",
        content: "",
        status: "streaming",
      },
    ];
    const { rerender } = render(<ProductSearchPage />, { wrapper });
    expect(screen.getByRole("status")).toBeTruthy();

    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-stream",
        content: "Here are red dresses",
        status: "streaming",
      },
    ];
    rerender(<ProductSearchPage />);
    expect(screen.getByText("Here are red dresses")).toBeTruthy();
  });

  it("should render markdown tables from assistant answers", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-md",
        content:
          "| # | Product | Color |\n|---|---|---|\n| 1 | Lace Bra | White |\n| 2 | Bralette | Black |",
        products: [],
        status: "streaming",
      },
    ];
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("Product")).toBeTruthy();
    expect(screen.getByText("Lace Bra")).toBeTruthy();
    expect(screen.getByText("Bralette")).toBeTruthy();
  });

  it("should retry a failed turn with the retry button", () => {
    mockChat.messages = [
      { ...viewFromChatMessage(historyMessages[0]!, 1), status: "failed", pairId: "p1" },
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-fail",
        status: "failed",
        error: "chat_failed",
        products: [],
        pairId: "p1",
      },
    ];
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByLabelText("Retry"));
    expect(mockChat.retry).toHaveBeenCalledWith(expect.objectContaining({ id: "m1" }));
  });

  it("should keep the error and retry button after a failed turn is saved", () => {
    mockChat.messages = [
      {
        id: "u-1",
        pairId: "pair-1",
        createdAt: 1,
        role: "user",
        kind: "message",
        content: "q",
        products: [],
        searchContext: null,
        debug: null,
        status: "saved",
        error: null,
      },
      {
        id: "a-1",
        pairId: "pair-1",
        createdAt: 2,
        role: "assistant",
        kind: "message",
        content: "",
        products: [],
        searchContext: null,
        debug: null,
        status: "saved",
        error: "embedding_failed",
      },
    ];
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("Search failed")).toBeTruthy();
    const retryButtons = screen.getAllByLabelText("Retry");
    expect(retryButtons.length).toBe(1);
    fireEvent.click(retryButtons[0]!);
    expect(mockChat.retry).toHaveBeenCalledTimes(1);
  });

  it("should copy the user message text when clicking the copy button", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByLabelText("Copy"));
    expect(writeText).toHaveBeenCalledWith("i want short dress");
    expect(await screen.findByText("Copied!")).toBeTruthy();
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("should fall back to execCommand when the clipboard API is unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    const execCopy = vi.fn(() => true);
    document.execCommand = execCopy;
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByLabelText("Copy"));
    expect(await screen.findByText("Copied!")).toBeTruthy();
    expect(execCopy).toHaveBeenCalledWith("copy");
  });

  it("should open the debug dialog from the assistant bubble and show prompt/response", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        debug: {
          prompt: { model: "gpt-4o", messages: [{ role: "user", content: "hi" }] },
          response: { choices: [{ message: { content: "ok" } }] },
        },
      },
    ];
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByLabelText("Debug"));
    expect(screen.getByText("LLM Debug Info")).toBeTruthy();
    expect(screen.getByText("Prompt")).toBeTruthy();
    expect(screen.getByText("Response")).toBeTruthy();
    expect(screen.getByText(/"gpt-4o"/)).toBeTruthy();

    fireEvent.click(screen.getByText("Close"));
    expect(screen.queryByText("LLM Debug Info")).toBeNull();
  });

  it("should disable input when viewing a closed conversation", () => {
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByText("Summer collection"));
    expect(screen.getByText("This conversation is closed and read-only.")).toBeTruthy();
    expect(chatOptions.blocked).toBe(true);
    expect(screen.getByPlaceholderText("Type your product query...")).toBeDisabled();
  });

  it("should show a retry button under an error-intent assistant response", () => {
    mockChat.messages = [
      {
        id: "u-1",
        pairId: "pair-1",
        createdAt: 1,
        role: "user",
        kind: "message",
        content: "q",
        products: [],
        searchContext: null,
        debug: null,
        status: "saved",
        error: null,
      },
      {
        id: "a-1",
        pairId: "pair-1",
        createdAt: 2,
        role: "assistant",
        kind: "message",
        content: "Sorry, our system could not process your request",
        products: [],
        searchContext: { rewritten_query: null, filters: null, intent: "error" },
        debug: null,
        status: "saved",
        error: null,
      },
    ];
    render(<ProductSearchPage />, { wrapper });
    const retryButtons = screen.getAllByLabelText("Retry");
    expect(retryButtons.length).toBe(1);
    fireEvent.click(retryButtons[0]!);
    expect(mockChat.retry).toHaveBeenCalledTimes(1);
  });

  it("should open and close the conversation list drawer on mobile", () => {
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByLabelText("Open conversations"));
    expect(screen.getByLabelText("Close")).toBeTruthy();
    expect(screen.getAllByText("Short dress hunt").length).toBe(2);
    fireEvent.click(screen.getByLabelText("Close"));
    expect(screen.queryByLabelText("Close")).toBeNull();
  });

  it("should close the drawer when selecting a conversation", () => {
    render(<ProductSearchPage />, { wrapper });
    fireEvent.click(screen.getByLabelText("Open conversations"));
    fireEvent.click(screen.getAllByText("Summer collection")[1]!);
    expect(screen.queryByLabelText("Close")).toBeNull();
  });

  it("should create a new conversation when none is active", async () => {
    chatsResult = { data: [conversationB], isLoading: false };
    createConversation.mockReturnValue({
      unwrap: () => Promise.resolve({ ...conversationA, id: "conv-c", title: null }),
    });
    render(<ProductSearchPage />, { wrapper });
    await waitFor(() => {
      expect(createConversation).toHaveBeenCalledWith({ locale: "en", createNew: true });
    });
  });

  it("should render localized product names on cards for Arabic locale", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-ar",
        content: "نعم",
        locale: "ar",
        status: "streaming",
        products: [
          {
            id: "p1",
            name: "Blue Top",
            name_ar: "توب أزرق",
            brand: "Zara",
            brand_ar: "زارا",
            price: 10,
            currency: "KWD",
            image_url: null,
            buy_url: null,
            store_id: "s1",
          },
        ],
      },
    ];
    uiLocale.value = "ar";
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("توب أزرق")).toBeTruthy();
    expect(screen.getByText("زارا")).toBeTruthy();
    expect(screen.queryByText("Blue Top")).toBeNull();
  });

  it("should render the response text below the product cards", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-ar",
        content: "Here are the results",
        locale: "ar",
        status: "streaming",
        products: [
          {
            id: "p1",
            name: "Blue Top",
            name_ar: "توب أزرق",
            brand: "Zara",
            brand_ar: "زارا",
            price: 10,
            currency: "KWD",
            image_url: null,
            buy_url: null,
            store_id: "s1",
          },
        ],
      },
    ];
    uiLocale.value = "ar";
    render(<ProductSearchPage />, { wrapper });
    const card = screen.getByText("توب أزرق");
    const text = screen.getByText("Here are the results");
    expect(card.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("should fall back to the English name when no localized name exists", () => {
    uiLocale.value = "ar";
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("Red Dress")).toBeTruthy();
  });

  it("should use the stream message language over the UI locale for cards", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-ar",
        content: "نعم",
        locale: "ar",
        status: "streaming",
        products: [
          {
            id: "p1",
            name: "Blue Top",
            name_ar: "توب أزرق",
            brand: "Zara",
            brand_ar: "زارا",
            price: 10,
            currency: "KWD",
            image_url: null,
            buy_url: null,
            store_id: "s1",
          },
        ],
      },
    ];
    uiLocale.value = "en";
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("توب أزرق")).toBeTruthy();
    expect(screen.getByText("زارا")).toBeTruthy();
    expect(screen.queryByText("Blue Top")).toBeNull();
  });

  it("should keep English card names when the message is English even on an Arabic UI", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-en",
        content: "ok",
        locale: "en",
        status: "streaming",
        products: [
          {
            id: "p1",
            name: "Blue Top",
            name_ar: "توب أزرق",
            brand: "Zara",
            brand_ar: "زارا",
            price: 10,
            currency: "KWD",
            image_url: null,
            buy_url: null,
            store_id: "s1",
          },
        ],
      },
    ];
    uiLocale.value = "ar";
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("Blue Top")).toBeTruthy();
    expect(screen.queryByText("توب أزرق")).toBeNull();
  });

  it("should use the saved message language for history cards", () => {
    const originalSnapshot = historyMessages[1]!.product_snapshots[0]!;
    historyMessages[1]!.locale = "ar";
    historyMessages[1]!.product_snapshots[0] = {
      id: "p1",
      name: "Red Dress",
      name_ar: "فستان أحمر",
      brand: "Brand A",
      brand_ar: "براند أ",
      price: 10,
      currency: "USD",
      image_url: null,
      buy_url: null,
      store_id: "s1",
    };
    uiLocale.value = "en";
    mockChat.messages = historyMessages.map((message, index) =>
      viewFromChatMessage(message, index + 1),
    );
    render(<ProductSearchPage />, { wrapper });
    expect(screen.getByText("فستان أحمر")).toBeTruthy();
    expect(screen.getByText("براند أ")).toBeTruthy();
    delete historyMessages[1]!.locale;
    historyMessages[1]!.product_snapshots[0] = originalSnapshot;
  });

  it("should show a fallback when a product image fails to load", () => {
    mockChat.messages = [
      viewFromChatMessage(historyMessages[0]!, 1),
      {
        ...viewFromChatMessage(historyMessages[1]!, 2),
        id: "a-img",
        content: "Here they are",
        status: "streaming",
        products: [
          {
            id: "p1",
            name: "Blue Top",
            brand: "Zara",
            price: 10,
            currency: "KWD",
            image_url: "https://cdn.example.com/blue-top.jpg",
            buy_url: null,
            store_id: "s1",
          },
        ],
      },
    ];
    render(<ProductSearchPage />, { wrapper });
    const first = screen.getByAltText("Blue Top") as HTMLImageElement;

    fireEvent.error(first);

    expect(screen.queryByAltText("Blue Top")).not.toBeInTheDocument();
    expect(screen.getByTitle("Blue Top")).toBeInTheDocument();
  });

  it("should delete a conversation after confirming in the dialog", async () => {
    deleteConversation.mockResolvedValue({ data: undefined });
    render(<ProductSearchPage />, { wrapper });
    const deleteButtons = screen.getAllByLabelText("Delete conversation");
    fireEvent.click(deleteButtons[0]!);
    expect(screen.getByText("Delete this conversation? This cannot be undone.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(deleteConversation).toHaveBeenCalledWith("conv-a");
    });
  });
});
