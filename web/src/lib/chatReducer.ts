import type { ChatMessage, ChatProduct } from "@/types/api";
import type { ChatViewMessage } from "@/lib/chatTypes";

export type ChatAction =
  | { type: "reset" }
  | {
      type: "appendTurn";
      pairId: string;
      createdAt: number;
      idempotencyKey: string;
      user: { content: string; kind: "message" | "similar" };
    }
  | { type: "streamStart"; searchContext: ChatMessage["search_context"] }
  | { type: "streamDebug"; debug: ChatMessage["debug"] }
  | { type: "streamChunk"; delta: string }
  | { type: "streamProducts"; products: ChatProduct[]; locale?: string }
  | { type: "streamComplete" }
  | { type: "streamFail"; code: string }
  | { type: "turnSaved"; pairId: string; assistant: ChatMessage | null; user: ChatMessage | null }
  | { type: "mergeHistory"; messages: ChatMessage[] }
  | { type: "retry"; pairId: string; createdAt: number };

const ACTIVE_STATUSES = ["pending", "streaming", "completed"] as const;

function isActiveAssistant(message: ChatViewMessage): boolean {
  return (
    message.role === "assistant" &&
    message.status !== "saved" &&
    message.status !== "failed" &&
    (ACTIVE_STATUSES as readonly string[]).includes(message.status)
  );
}

function sortByCreatedAt(messages: ChatViewMessage[]): ChatViewMessage[] {
  return messages.toSorted((a, b) => a.createdAt - b.createdAt);
}

function messageToView(message: ChatMessage, pairId: string, createdAt: number): ChatViewMessage {
  return {
    id: message.id,
    pairId,
    createdAt,
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

function patchActiveAssistant(
  state: ChatViewMessage[],
  patch: (message: ChatViewMessage) => ChatViewMessage,
): ChatViewMessage[] {
  const index = state.findLastIndex((message) => isActiveAssistant(message));
  if (index === -1) {
    return state;
  }
  const next = [...state];
  next[index] = patch(next[index]!);
  return next;
}

function appendTurnCase(
  state: ChatViewMessage[],
  action: Extract<ChatAction, { type: "appendTurn" }>,
): ChatViewMessage[] {
  const { pairId, createdAt, idempotencyKey, user } = action;
  return sortByCreatedAt([
    ...state,
    {
      id: `u-${pairId}`,
      pairId,
      createdAt,
      role: "user",
      kind: user.kind,
      content: user.content,
      products: [],
      searchContext: null,
      debug: null,
      status: "pending",
      error: null,
      idempotencyKey,
    },
    {
      id: `a-${pairId}`,
      pairId,
      createdAt: createdAt + 1,
      role: "assistant",
      kind: "message",
      content: "",
      products: [],
      searchContext: null,
      debug: null,
      status: "streaming",
      error: null,
    },
  ]);
}

function streamStartCase(
  state: ChatViewMessage[],
  searchContext: ChatMessage["search_context"],
): ChatViewMessage[] {
  return patchActiveAssistant(state, (message) => ({ ...message, searchContext }));
}

function streamDebugCase(state: ChatViewMessage[], debug: ChatMessage["debug"]): ChatViewMessage[] {
  return patchActiveAssistant(state, (message) => ({ ...message, debug }));
}

function streamChunkCase(state: ChatViewMessage[], delta: string): ChatViewMessage[] {
  return patchActiveAssistant(state, (message) => ({
    ...message,
    content: message.content + delta,
  }));
}

function streamProductsCase(
  state: ChatViewMessage[],
  products: ChatProduct[],
  locale?: string,
): ChatViewMessage[] {
  return patchActiveAssistant(state, (message) => ({
    ...message,
    products,
    ...(locale ? { locale } : {}),
  }));
}

function streamCompleteCase(state: ChatViewMessage[]): ChatViewMessage[] {
  return patchActiveAssistant(state, (message) =>
    message.status === "streaming" ? { ...message, status: "completed" } : message,
  );
}

function streamFailCase(state: ChatViewMessage[], code: string): ChatViewMessage[] {
  const index = state.findLastIndex(
    (message) => message.role === "assistant" && !["saved", "failed"].includes(message.status),
  );
  if (index === -1) {
    return state;
  }
  const assistant = state[index]!;
  const userIndex = state.findLastIndex(
    (message) => message.role === "user" && message.pairId === assistant.pairId,
  );
  const next = [...state];
  next[index] = { ...assistant, status: "failed", error: code };
  if (userIndex !== -1) {
    next[userIndex] = { ...next[userIndex]!, status: "failed" };
  }
  return next;
}

function turnSavedCase(
  state: ChatViewMessage[],
  action: Extract<ChatAction, { type: "turnSaved" }>,
): ChatViewMessage[] {
  const { pairId, assistant, user } = action;
  const replaced = state.map((message) => {
    if (message.pairId !== pairId) {
      return message;
    }
    const idempotencyKey = message.idempotencyKey;
    if (message.role === "assistant") {
      const saved = assistant
        ? messageToView(assistant, pairId, message.createdAt)
        : { ...message, status: "saved" as const };
      return idempotencyKey ? { ...saved, idempotencyKey } : saved;
    }
    if (user) {
      const saved = messageToView(user, pairId, message.createdAt);
      return idempotencyKey ? { ...saved, idempotencyKey } : saved;
    }
    const saved = { ...message, status: "saved" as const };
    return idempotencyKey ? { ...saved, idempotencyKey } : saved;
  });
  return sortByCreatedAt(replaced);
}

function mergeHistoryCase(state: ChatViewMessage[], history: ChatMessage[]): ChatViewMessage[] {
  const existingById = new Map(state.map((message) => [message.id, message]));
  let next = [...state];
  for (const historyMessage of history) {
    const existing = existingById.get(historyMessage.id);
    if (existing) {
      if (existing.status !== "saved") {
        continue;
      }
      next = next.map((message) =>
        message.id === historyMessage.id
          ? messageToView(historyMessage, message.pairId, message.createdAt)
          : message,
      );
      continue;
    }
    const createdAt = new Date(historyMessage.created_at).getTime();
    next.push(messageToView(historyMessage, `h-${historyMessage.id}`, createdAt));
  }
  return sortByCreatedAt(next);
}

function retryCase(
  state: ChatViewMessage[],
  action: Extract<ChatAction, { type: "retry" }>,
): ChatViewMessage[] {
  const index = state.findLastIndex(
    (message) => message.role === "user" && message.pairId === action.pairId,
  );
  if (index === -1) {
    return state;
  }
  const pairId = action.pairId;
  const next = state.map((message) => {
    if (message.pairId !== pairId) {
      return message;
    }
    return message.role === "user"
      ? { ...message, status: "pending" as const }
      : {
          ...message,
          status: "streaming" as const,
          content: "",
          products: [],
          searchContext: null,
          debug: null,
          error: null,
        };
  });
  return sortByCreatedAt(next);
}

export function chatReducer(state: ChatViewMessage[], action: ChatAction): ChatViewMessage[] {
  switch (action.type) {
    case "reset": {
      return [];
    }
    case "appendTurn": {
      return appendTurnCase(state, action);
    }
    case "streamStart": {
      return streamStartCase(state, action.searchContext);
    }
    case "streamDebug": {
      return streamDebugCase(state, action.debug);
    }
    case "streamChunk": {
      return streamChunkCase(state, action.delta);
    }
    case "streamProducts": {
      return streamProductsCase(state, action.products, action.locale);
    }
    case "streamComplete": {
      return streamCompleteCase(state);
    }
    case "streamFail": {
      return streamFailCase(state, action.code);
    }
    case "turnSaved": {
      return turnSavedCase(state, action);
    }
    case "mergeHistory": {
      return mergeHistoryCase(state, action.messages);
    }
    case "retry": {
      return retryCase(state, action);
    }
    default: {
      return state;
    }
  }
}

export function mergeHistory(
  messages: ChatViewMessage[],
  history: ChatMessage[],
): ChatViewMessage[] {
  return chatReducer(messages, { type: "mergeHistory", messages: history });
}
