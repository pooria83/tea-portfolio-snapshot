import type { ChatMessage, ChatProduct } from "@/types/api";

export type ChatViewStatus = "pending" | "streaming" | "completed" | "failed" | "saved";

export interface ChatViewMessage {
  /** Server message id once persisted; the temp id while optimistic. */
  id: string;
  /** Stable client id shared by both messages of a turn (retry pairing). */
  pairId: string;
  /** Creation hint (Date.now()) used to keep list order across merges. */
  createdAt: number;
  role: "user" | "assistant";
  kind: "message" | "similar";
  content: string;
  products: ChatProduct[];
  locale?: string;
  searchContext: ChatMessage["search_context"];
  debug: ChatMessage["debug"];
  status: ChatViewStatus;
  /** Localized error code when the turn failed. */
  error: string | null;
  /** Idempotency key of the turn — reused verbatim on retry. */
  idempotencyKey?: string;
}

export interface ChatViewTurn {
  user: ChatViewMessage;
  assistant: ChatViewMessage;
}
