"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";

import { useChatSocket, type ChatSocketStatus } from "@/hooks/useChatSocket";
import { chatReducer } from "@/lib/chatReducer";
import { errorCodeFromFrame, sendMessageFrame, sendSimilarRequestFrame } from "@/lib/chatStream";
import type { ChatViewMessage } from "@/lib/chatTypes";
import type { ChatMessage, ChatProduct } from "@/types/api";

interface UseChatOptions {
  conversationId: string | null;
  tokenOverride?: string | null;
  /** Prevents sending and find-similar while true (e.g. closed conversation). */
  blocked?: boolean;
  /** Called after a turn was persisted server-side (e.g. refresh the chat list). */
  onTurnSaved?: () => void;
}

interface UseChatResult {
  messages: ChatViewMessage[];
  status: ChatSocketStatus;
  /** True when a message/similar turn can be started right now. */
  canSend: boolean;
  /** True while the assistant is streaming the active turn. */
  streaming: boolean;
  sendMessage: (content: string) => boolean;
  sendSimilar: (product: ChatProduct, productName: string) => boolean;
  retry: (message: ChatViewMessage) => boolean;
  /** Merge persisted history into the list (deduped by server id). */
  mergeHistory: (messages: ChatMessage[]) => void;
  reset: () => void;
}

/**
 * Central chat state machine: owns the ordered message list, the send lock
 * (double-submit protection), optimistic turns, stream frame merging and the
 * persisted-turn reconciliation. Used by both the admin and anonymous chats.
 */
export function useChat({
  conversationId,
  tokenOverride,
  blocked = false,
  onTurnSaved,
}: UseChatOptions): UseChatResult {
  const [messages, dispatch] = useReducer(chatReducer, []);
  const sendLockRef = useRef(false);
  const activePairRef = useRef("");
  const onTurnSavedRef = useRef(onTurnSaved);

  useEffect(() => {
    onTurnSavedRef.current = onTurnSaved;
  }, [onTurnSaved]);

  const handleFrame = useCallback((frame: Record<string, unknown>) => {
    switch (frame.type) {
      case "assistant_start": {
        const searchContext = (frame.search_context as ChatMessage["search_context"]) ?? null;
        dispatch({ type: "streamStart", searchContext });
        break;
      }
      case "debug": {
        const debug = (frame.debug as ChatMessage["debug"]) ?? null;
        dispatch({ type: "streamDebug", debug });
        break;
      }
      case "text_chunk": {
        const delta = typeof frame.delta === "string" ? frame.delta : "";
        if (delta) {
          dispatch({ type: "streamChunk", delta });
        }
        break;
      }
      case "product_cards": {
        const products = Array.isArray(frame.products) ? (frame.products as ChatProduct[]) : [];
        const locale = typeof frame.locale === "string" ? frame.locale : undefined;
        dispatch({ type: "streamProducts", products, ...(locale ? { locale } : {}) });
        break;
      }
      case "assistant_end": {
        sendLockRef.current = false;
        dispatch({ type: "streamComplete" });
        break;
      }
      case "error": {
        sendLockRef.current = false;
        dispatch({ type: "streamFail", code: errorCodeFromFrame(frame) ?? "chat_failed" });
        break;
      }
      case "message_saved": {
        sendLockRef.current = false;
        const assistant = frame.message as ChatMessage | undefined;
        const user = frame.user_message as ChatMessage | null | undefined;
        dispatch({
          type: "turnSaved",
          pairId: activePairRef.current,
          assistant: assistant ?? null,
          user: user ?? null,
        });
        onTurnSavedRef.current?.();
        break;
      }
      default: {
        break;
      }
    }
  }, []);

  const { status, sendFrame } = useChatSocket({
    conversationId,
    ...(tokenOverride ? { tokenOverride } : {}),
    onFrame: handleFrame,
  });

  const streaming = useMemo(
    () => messages.some((message) => message.status === "streaming"),
    [messages],
  );
  const hasPending = useMemo(
    () => messages.some((message) => message.status === "pending"),
    [messages],
  );

  const canSend = useMemo(
    () => status === "open" && !blocked && !streaming && !hasPending,
    [status, blocked, streaming, hasPending],
  );

  useEffect(() => {
    sendLockRef.current = false;
    activePairRef.current = "";
    dispatch({ type: "reset" });
  }, [conversationId]);

  const sendMessage = useCallback(
    (content: string) => {
      if (status !== "open" || blocked || streaming || hasPending || sendLockRef.current) {
        console.warn("chat_send_blocked");
        return false;
      }
      const pairId = crypto.randomUUID();
      const idempotencyKey = crypto.randomUUID();
      activePairRef.current = pairId;
      sendLockRef.current = true;
      dispatch({
        type: "appendTurn",
        pairId,
        createdAt: Date.now(),
        idempotencyKey,
        user: { content, kind: "message" },
      });
      sendFrame(sendMessageFrame(content, idempotencyKey));
      return true;
    },
    [status, blocked, streaming, hasPending, sendFrame],
  );

  const sendSimilar = useCallback(
    (product: ChatProduct, productName: string) => {
      if (status !== "open" || blocked || streaming || hasPending || sendLockRef.current) {
        console.warn("chat_send_blocked");
        return false;
      }
      const pairId = crypto.randomUUID();
      const idempotencyKey = crypto.randomUUID();
      activePairRef.current = pairId;
      sendLockRef.current = true;
      dispatch({
        type: "appendTurn",
        pairId,
        createdAt: Date.now(),
        idempotencyKey,
        user: { content: productName, kind: "similar" },
      });
      sendFrame(sendSimilarRequestFrame(product.id, idempotencyKey, productName));
      return true;
    },
    [status, blocked, streaming, hasPending, sendFrame],
  );

  const retry = useCallback(
    (message: ChatViewMessage) => {
      if (status !== "open" || blocked || streaming || hasPending || sendLockRef.current) {
        console.warn("chat_send_blocked");
        return false;
      }
      const idempotencyKey = message.idempotencyKey ?? crypto.randomUUID();
      activePairRef.current = message.pairId;
      sendLockRef.current = true;
      dispatch({ type: "retry", pairId: message.pairId, createdAt: Date.now() });
      sendFrame(sendMessageFrame(message.content, idempotencyKey));
      return true;
    },
    [status, blocked, streaming, hasPending, sendFrame],
  );

  const mergeHistory = useCallback((history: ChatMessage[]) => {
    dispatch({ type: "mergeHistory", messages: history });
  }, []);

  const reset = useCallback(() => {
    sendLockRef.current = false;
    activePairRef.current = "";
    dispatch({ type: "reset" });
  }, []);

  return {
    messages,
    status,
    canSend,
    streaming,
    sendMessage,
    sendSimilar,
    retry,
    mergeHistory,
    reset,
  };
}
