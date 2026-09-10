"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { parseChatFrame } from "@/lib/chatStream";

export type ChatSocketStatus = "idle" | "connecting" | "open" | "closed" | "reconnecting";

interface UseChatSocketOptions {
  conversationId: string | null;
  tokenOverride?: string | null;
  onFrame: (frame: Record<string, unknown>) => void;
}

type PendingFrame = string;

const PING_INTERVAL_MS = 30_000;
const MAX_BACKOFF_MS = 30_000;
const MAX_MISSED_PINGS = 2;

function buildWsUrl(apiBase: string, conversationId: string): string {
  const base = apiBase.replace(/\/+$/, "");
  const scheme = base.startsWith("https") ? "wss" : "ws";
  const hostAndPath = base.replace(/^https?:\/\//, "");
  return `${scheme}://${hostAndPath}/ws/chat/${conversationId}`;
}

/**
 * Pure chat WebSocket transport: connects, pings, reconnects with backoff and
 * flushes one queued frame after (re)connect. Frame parsing is left to the
 * caller via the `onFrame` listener — this hook owns no message state.
 */
export function useChatSocket({ conversationId, tokenOverride, onFrame }: UseChatSocketOptions) {
  const token = tokenOverride ?? null;
  const [status, setStatus] = useState<ChatSocketStatus>(() =>
    conversationId ? "connecting" : "idle",
  );
  const socketRef = useRef<WebSocket | null>(null);
  const pendingFrameRef = useRef<PendingFrame | null>(null);
  const onFrameRef = useRef(onFrame);
  const missedPingsRef = useRef(0);

  useEffect(() => {
    onFrameRef.current = onFrame;
  }, [onFrame]);

  useEffect(() => {
    if (!conversationId) {
      return;
    }

    const activeConversationId: string = conversationId;
    const activeToken: string | null = token;
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let pingTimer: ReturnType<typeof setInterval> | null = null;
    let attempt = 0;
    let disposed = false;

    const clearTimers = () => {
      if (retryTimer !== null) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      if (pingTimer !== null) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const stopPing = () => {
      if (pingTimer !== null) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const startPing = () => {
      stopPing();
      pingTimer = setInterval(() => {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          return;
        }
        socket.send(JSON.stringify({ type: "ping" }));
        missedPingsRef.current += 1;
        if (missedPingsRef.current >= MAX_MISSED_PINGS) {
          socket.close();
        }
      }, PING_INTERVAL_MS);
    };

    const flushPending = () => {
      const pending = pendingFrameRef.current;
      if (!pending || !socket || socket.readyState !== WebSocket.OPEN) {
        return;
      }
      pendingFrameRef.current = null;
      socket.send(pending);
    };

    const handleOpen = () => {
      attempt = 0;
      missedPingsRef.current = 0;
      setStatus("open");
      startPing();
      flushPending();
    };

    const scheduleRetry = () => {
      if (disposed) {
        return;
      }
      const delay = Math.min(1000 * 2 ** attempt, MAX_BACKOFF_MS);
      attempt += 1;
      setStatus("reconnecting");
      retryTimer = setTimeout(connect, delay);
    };

    const handleClose = (event: CloseEvent) => {
      stopPing();
      if (disposed) {
        return;
      }
      if (event.code === 4001) {
        setStatus("closed");
        return;
      }
      scheduleRetry();
    };

    const handleError = () => {
      // The close event always follows; reconnection is scheduled there.
    };

    const handleMessage = (event: MessageEvent<string>) => {
      const frame = parseChatFrame(event.data);
      if (!frame) {
        console.warn("chat_ws_invalid_frame");
        return;
      }
      missedPingsRef.current = 0;
      onFrameRef.current?.(frame);
    };

    function connect() {
      if (disposed) {
        return;
      }
      setStatus("connecting");
      const protocols = activeToken ? [activeToken] : undefined;
      socket = new WebSocket(buildWsUrl(apiBase, activeConversationId), protocols);
      socketRef.current = socket;
      socket.addEventListener("open", handleOpen);
      socket.addEventListener("close", handleClose);
      socket.addEventListener("error", handleError);
      socket.addEventListener("message", handleMessage);
    }

    const handleVisibility = () => {
      if (document.visibilityState !== "visible" || disposed) {
        return;
      }
      const current = socketRef.current;
      if (
        !current ||
        current.readyState === WebSocket.CLOSED ||
        current.readyState === WebSocket.CLOSING
      ) {
        attempt = 0;
        clearTimers();
        connect();
      }
    };

    connect();
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      disposed = true;
      clearTimers();
      document.removeEventListener("visibilitychange", handleVisibility);
      if (socket) {
        socket.removeEventListener("open", handleOpen);
        socket.removeEventListener("close", handleClose);
        socket.removeEventListener("error", handleError);
        socket.removeEventListener("message", handleMessage);
        socket.close();
      }
      socketRef.current = null;
      pendingFrameRef.current = null;
      setStatus("idle");
    };
  }, [conversationId, token]);

  const sendFrame = useCallback((frame: string) => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(frame);
      return;
    }
    pendingFrameRef.current = frame;
  }, []);

  return { status, sendFrame };
}
